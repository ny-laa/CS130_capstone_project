# POST /api/chat — web UI chat endpoint.
# Full agent path: auth → persist → history → context → Claude → tools → DB → reply.
# Mirrors the SMS webhook flow so both channels share the same orchestrator/runner/tools.

import json
import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from adapters.communication.sms_tool import SMSTool
from adapters.google.user_calendar_adapter import UserCalendarAdapter
from adapters.google.user_gmail_adapter import UserGmailAdapter
from adapters.llm.claude_adapter import ClaudeAdapter
from database import get_db
from models.datatypes import MessageDirection, TaskStatus, Tools
from orchestrator.orchestrator import GOrchestrator
from orchestrator.task_planner import PlanStep, StructuredTaskPlan
from orchestrator.task_planner import Task as InMemoryTask
from services import task_service
from services.auth_service import decode_token
from services.message_service import log_message, get_messages_for_user
from services.user_context_service import build_user_context
from services.user_service import get_user_by_id
from workers.task_runner import TaskRunner

router = APIRouter()
logger = logging.getLogger("backend.api.chat")

_llm = ClaudeAdapter(model="claude-haiku-4-5-20251001")
_sms = SMSTool()
_orch = GOrchestrator()

# [GenAI Use] Prompt: write a chat system prompt for G that matches the sms one — same JSON schema with task_type, description, plan_steps, response_message. chat can be slightly longer than sms, conversational tone. also needs to handle smalltalk as a no-op task type
# [GenAI Use] LLM Response Start
_CHAT_SYSTEM_PROMPT = """You are G, an AI personal secretary helping a parent over chat.
Your response_message should be conversational — no markdown, no bullet points.

Respond with a JSON object only, no extra text:
{
    "task_type": "<one of: reminder, calendar_update, information_request, morning_digest, smalltalk>",
    "description": "<short summary of what the parent is asking for>",
    "plan_steps": [
        {"tool": "<tool name>", "params": {}, "status": "PENDING"}
    ],
    "response_message": "<friendly reply to send back to the parent>"
}

Use smalltalk when the parent is just chatting and no tools are needed — leave plan_steps empty.
The current time is provided in the context as current_time_iso.
Tools you can use: sms_tool, calendar_tool, gmail_tool, call_tool"""

# After tools execute, synthesize a natural reply from the results.
_SYNTHESIS_PROMPT = 'You are G, a helpful AI secretary. Respond with ONLY valid JSON: {"response_message": "<short friendly reply>"}'
# [GenAI Use] LLM Response End
# [GenAI Use] Reflection: same JSON contract as SMS keeps the orchestrator happy. smalltalk escape hatch stops every "hi" from creating a DB task

_TASK_TYPE_LABEL = {
    "reminder": "Reminder",
    "calendar_update": "Calendar",
    "information_request": "Escalation",
    "morning_digest": "Reminder",
}


class ChatRequest(BaseModel):
    message: str
    user_id: str | None = None  # fallback if no auth header
    messages: list[dict] | None = None  # full in-session history from frontend (fallback when not logged in)


def _resolve_user(request: Request, body_user_id: str | None, db: Session):
    # prefer JWT from Authorization header; fall back to body user_id for unauthenticated demo
    # TODO: require auth once frontend login is mandatory on the chat page
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        user_id = decode_token(auth_header[7:])
        if user_id:
            return get_user_by_id(db, user_id)
    if body_user_id:
        try:
            return get_user_by_id(db, UUID(body_user_id))
        except (ValueError, AttributeError):
            pass
    return None


def _build_history(messages) -> list[dict]:
    # messages arrive newest-first from DB; reverse to chronological for Claude
    chrono = list(reversed(messages))
    history = []
    for m in chrono:
        role = "user" if m.direction == MessageDirection.INBOUND else "assistant"
        history.append({"role": role, "content": m.content})
    return history


def _collect_tool_results(plan_steps) -> list[dict]:
    results = []
    for step in plan_steps:
        if getattr(step, "result", None) is not None:
            results.append({"tool": step.tool, "result": step.result})
    return results


# [GenAI Use] Prompt: write the full /api/chat handler. it should: resolve user from jwt or body fallback, load last 20 messages as history, build user context, call claude with history+context, if smalltalk just return reply, otherwise create db task + run taskrunner with calendar/gmail/sms adapters, if escalation return escalated flag, if tools finished do a second claude call to synthesize results into natural reply. log everything
# [GenAI Use] LLM Response Start
@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request, db: Session = Depends(get_db)):
    logger.info("chat inbound message received: %.80r", body.message)

    user = _resolve_user(request, body.user_id, db)

    # load history before persisting so current message isn't double-counted
    history: list[dict] = []
    if user:
        prior_messages = get_messages_for_user(db, user.id, limit=20)
        history = _build_history(prior_messages)
        logger.info("user_id=%s history_messages=%d loaded from DB", user.id, len(history))
        try:
            log_message(db, content=body.message, direction="inbound",
                        channel="chat", user_id=user.id)
        except Exception as exc:
            logger.warning("failed to persist inbound message: %s", exc)
    elif body.messages and len(body.messages) > 1:
        # not logged in — use the in-session messages the frontend already has
        prior = body.messages[:-1]  # exclude current turn (last item)
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in prior
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        logger.info("no user — using %d in-session messages as history", len(history))

    # build context
    context: dict = {"current_time_iso": datetime.now().astimezone().isoformat()}
    if user:
        try:
            context.update(build_user_context(db, user.id))
            logger.info("user_id=%s user_context loaded", user.id)
        except Exception as exc:
            logger.warning("user_context build failed: %s", exc)

    # call Claude
    logger.info("calling Claude, history_turns=%d", len(history))
    try:
        plan = _llm.handle(body.message, _CHAT_SYSTEM_PROMPT, context=context, history=history)
    except Exception as exc:
        logger.error("Claude call failed: %s", exc)
        return {"reply": "Sorry, I had trouble with that. Try again?"}

    task_type = plan.get("task_type", "smalltalk")
    reply = (plan.get("response_message") or "").strip() or "Got it."
    plan_steps_raw = plan.get("plan_steps") or []

    # smalltalk or no steps → direct reply, no task needed
    if task_type == "smalltalk" or not plan_steps_raw:
        logger.info("direct reply (no task), task_type=%s", task_type)
        _persist_assistant_reply(db, user, reply)
        return _format_response(reply, plan, task_type, task_id=None, escalated=False)

    logger.info("task path: task_type=%s steps=%d", task_type, len(plan_steps_raw))

    # create DB task
    db_task = None
    if user:
        try:
            db_task = task_service.create_task(
                db,
                user_id=user.id,
                task_type=task_type,
                description=plan.get("description", body.message[:120]),
                plan_steps=plan_steps_raw,
            )
        except Exception as exc:
            logger.error("task persistence failed: %s", exc)

    # build in-memory task for TaskRunner
    steps = [
        PlanStep(tool=s["tool"], params=s.get("params", {}), status=TaskStatus.PENDING)
        for s in plan_steps_raw
    ]
    plan_obj = StructuredTaskPlan(
        task_type=task_type,
        description=plan.get("description", ""),
        plan_steps=steps,
        response_message=reply,
    )
    in_mem = InMemoryTask(
        id=db_task.id if db_task else None,
        user_id=user.id if user else None,
        status=TaskStatus.PENDING,
        task_plan=plan_obj,
        escalation_deadline=None,
        created_at=None,
        updated_at=None,
    )

    # wire tool registry — user-scoped adapters so no db needed inside runner
    tool_registry = {Tools.SMS_TOOL: _sms}
    if user:
        tool_registry[Tools.CALENDAR_TOOL] = UserCalendarAdapter(user)
        tool_registry[Tools.GMAIL_TOOL] = UserGmailAdapter(user)

    escalated = False
    try:
        TaskRunner(tool_registry).run(in_mem)
        if db_task:
            task_service.update_task_status(db, db_task.id, in_mem.status)
            task_service.update_plan_steps(db, db_task.id, in_mem.task_plan.plan_steps)

        if in_mem.status == TaskStatus.ESCALATION_PENDING:
            escalated = True
            logger.info("task_id=%s escalation_pending", db_task.id if db_task else "?")
            reply = (
                f"{reply}\n\nThis action needs your approval — check the Tasks tab."
            )
        else:
            # synthesize a reply that incorporates actual tool results
            tool_results = _collect_tool_results(in_mem.task_plan.plan_steps)
            if tool_results:
                logger.info("task_id=%s synthesizing reply from %d tool results", db_task.id if db_task else "?", len(tool_results))
                try:
                    synthesis_query = (
                        f"The user asked: '{body.message}'. "
                        f"Tool results: {json.dumps(tool_results, default=str)}. "
                        "Write a short friendly reply that directly answers the user using these results."
                    )
                    synthesis = _llm.handle(synthesis_query, _SYNTHESIS_PROMPT)
                    reply = (synthesis.get("response_message") or reply).strip() or reply
                except Exception as exc:
                    logger.warning("synthesis call failed, using original reply: %s", exc)

    except Exception as exc:
        logger.error("TaskRunner failed: %s", exc)
        if db_task:
            try:
                task_service.update_task_status(db, db_task.id, TaskStatus.FAILED)
            except Exception:
                pass
        reply = "I ran into a problem completing that. Please try again."

    _persist_assistant_reply(db, user, reply, task_id=db_task.id if db_task else None)
    return _format_response(reply, plan, task_type, task_id=str(db_task.id) if db_task else None, escalated=escalated)
# [GenAI Use] LLM Response End
# [GenAI Use] Reflection: mirrors the sms webook flow closely. the second claude synthesis call is new — lets the reply actually use calendar/gmail results instead of ignoring them. escalation falls through the same flag as sms path


def _persist_assistant_reply(db: Session, user, reply: str, task_id=None) -> None:
    if not user:
        return
    try:
        log_message(
            db,
            content=reply,
            direction="outbound",
            channel="chat",
            user_id=user.id,
            task_id=task_id,
        )
        logger.info("user_id=%s assistant reply persisted", user.id)
    except Exception as exc:
        logger.warning("failed to persist assistant reply: %s", exc)


def _format_response(reply: str, plan: dict, task_type: str, task_id: str | None, escalated: bool) -> dict:
    description = plan.get("description")
    if task_type and task_type != "smalltalk" and description:
        label = _TASK_TYPE_LABEL.get(task_type, "Reminder")
        reply = (
            f"{reply}\n<task>"
            f"<type>{label}</type>"
            f"<status>{'Needs Approval' if escalated else 'Pending'}</status>"
            f"<description>{description}</description>"
            f"<summary>{description[:80]}</summary>"
            f"</task>"
        )
    return {"reply": reply, "task_id": task_id, "escalated": escalated}
