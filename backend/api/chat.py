# POST /api/chat — web UI chat endpoint.
# Full agent path: auth → persist → history → context → Claude → tools → DB → reply.
# Mirrors the SMS webhook flow so both channels share the same orchestrator/runner/tools.

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from adapters.communication.business_call_tool import UserBusinessCallAdapter
from adapters.communication.call_tool import OutboundCallTool
from adapters.communication.sms_tool import SMSTool
from adapters.communication.user_call_adapter import UserCallAdapter
from adapters.communication.user_sms_adapter import UserSMSAdapter
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
_call = OutboundCallTool()
_orch = GOrchestrator()

# [GenAI Use] Prompt: write a chat system prompt for G that matches the sms one — same JSON schema with task_type, description, plan_steps, response_message. chat can be slightly longer than sms, conversational tone. also needs to handle smalltalk as a no-op task type
# [GenAI Use] LLM Response Start
_CHAT_SYSTEM_PROMPT = '''You are G, an AI personal secretary helping a parent over chat.
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
Tools you can use: sms_tool, calendar_tool, gmail_tool, call_tool, business_call_tool

`business_call_tool` is used when the parent asks you to phone an external business or person on their behalf (e.g. "call the pizza place and order a large pepperoni", "call my doctor\'s office and reschedule"). Params: `to` (the business phone number, E.164 if available), `goal` (one sentence describing exactly what to accomplish — include any order details, addresses, times the parent gave you), and optionally `business_name`. Only plan a business_call_tool step when the parent supplied a phone number or a business clearly identifiable from context; if you don\'t have a number, ask the parent for one instead of guessing.

When to ask a clarifying question FIRST instead of acting:
You are a capable assistant — that means you should pause and think before committing on the parent\'s behalf, especially for irreversible or high-stakes actions. If anything material is missing or ambiguous for one of these, do NOT plan the step yet. Set task_type="smalltalk", leave plan_steps empty, and use response_message to ask the specific question(s) you need answered:
  - business_call_tool: ALWAYS verify before placing the call — confirm the destination number, the exact details that go into `goal` (items, address, time, payment notes), and that the parent actually wants you to call right now. A phone call costs money, takes real time on someone\'s line, and commits to whatever you say.
  - Purchases, paid bookings, or anything spending money on the parent\'s behalf — confirm amount, merchant, and any preferences.
  - Calendar deletes or updates where you\'re not sure which event the parent means — ask which one.
  - Outbound messages or calls to third parties (other family members, providers) where the recipient isn\'t obvious.
Lower-stakes actions (reminders to the parent themselves, adding a personal calendar event with clear details, reading gmail, sending the parent an SMS reminder) can proceed without clarification — don\'t pester them. Judgment call: would a thoughtful human assistant double-check before doing this?

The current time is provided in the context as `current_time_iso` (ISO 8601 with timezone offset). Always calculate relative times from current_time_iso exactly. Do not use UTC unless current_time_iso is UTC. Preserve the timezone offset from current_time_iso in scheduled_at. For sms_tool, call_tool, AND business_call_tool, when the parent asks you to do the action *later* -- either an absolute time ("at 5pm", "tomorrow at 8am") OR a relative duration ("in 30 minutes", "in 2 hours") -- set `params.scheduled_at` to the absolute ISO 8601 timestamp (same timezone as `current_time_iso`) when it should fire. Examples: if current_time_iso is "2026-05-31T18:48:00-07:00" and the parent says "in 2 minutes", scheduled_at is "2026-05-31T18:50:00-07:00". If they say "at 6:55", it\'s "2026-05-31T18:55:00-07:00". Omit `scheduled_at` only when the parent wants the action to happen right now. Scheduled actions persist in the DB and fire later via the worker, so you can confirm scheduling immediately in your reply.

If the user gives an ambiguous hour like "9:00": pick the closest future time by calculating the gap to both 9:00 AM and 9:00 PM and scheduling for whichever is sooner.
'''

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
    USER_TIMEZONE = ZoneInfo("America/Los_Angeles")

    context: dict = {
        "current_time_iso": datetime.now(USER_TIMEZONE).isoformat(),
        "timezone": "America/Los_Angeles",
    }
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
        return {"reply": f"Claude failed: {exc}"}
        #return {"reply": "Sorry, I had trouble with that. Try again?"}

    task_type = plan.get("task_type", "smalltalk")
    reply = (plan.get("response_message") or "").strip() or "Got it."
    plan_steps_raw = plan.get("plan_steps") or []

    # smalltalk or no steps → direct reply, no task needed
    if task_type == "smalltalk" and not plan_steps_raw:
        logger.info("direct reply (no task), task_type=%s", task_type)
        _persist_assistant_reply(db, user, reply)
        return _format_response(reply, plan, task_type, task_id=None, escalated=False)

    logger.info("task path: task_type=%s steps=%d", task_type, len(plan_steps_raw))

    # If any step has scheduled_at, route the whole plan through dispatch.run_plan.
    # That's the reminders framework: it creates the Task row(s), dedupes/merges
    # duplicate ETAs, and enqueues notify_user_task with eta= so celery fires the
    # SMS/call at the right time. TaskRunner doesn't know about scheduling and
    # would fire immediately, which is the bug we hit before.
    # sms_tool, call_tool, and business_call_tool are all schedulable via
    # dispatch -> celery (notify_user_task or run_plan_step_task depending
    # on the tool). when claude attaches scheduled_at to one of these, we
    # take the dispatch path; otherwise the plan runs inline through
    # TaskRunner.
    _SCHEDULABLE_TOOLS = ("sms_tool", "call_tool", "business_call_tool")
    has_scheduled_step = any(
        isinstance(s, dict)
        and s.get("tool") in _SCHEDULABLE_TOOLS
        and (s.get("params") or {}).get("scheduled_at")
        for s in plan_steps_raw
    )
    if user and has_scheduled_step:
        from services.dispatch import run_plan as dispatch_run_plan
        logger.info("scheduled step detected — routing via dispatch.run_plan (celery)")
        try:
            dispatch_results = dispatch_run_plan(plan, user, db)
            # grab the task_id dispatch created for the first scheduled step so
            # the response can point at it (frontend uses task_id for the banner).
            scheduled_task_id = next(
                (r.get("task_id") for r in dispatch_results if r.get("task_id")),
                None,
            )
        except Exception as exc:
            logger.error("dispatch.run_plan failed: %s", exc)
            scheduled_task_id = None
            reply = "I ran into a problem scheduling that. Please try again."
        _persist_assistant_reply(db, user, reply, task_id=None)
        return _format_response(reply, plan, task_type, task_id=scheduled_task_id, escalated=False)

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
    # comm tools are per-user so the adapter can inject `to=user.phone_number`
    # before calling the underlying Twilio client -- claude isn't expected
    # to know the user's number, so the base SMSTool / OutboundCallTool
    # KeyError on params["to"] when used directly. UserSMSAdapter /
    # UserCallAdapter handle the binding. Fall back to the raw singletons
    # when there's no user (unauthenticated demo); claude shouldn't ever
    # plan an sms/call step in that mode anyway, but if it does, the raw
    # tool will surface a clear error instead of a silent failure.
    if user:
        tool_registry = {
            Tools.SMS_TOOL: UserSMSAdapter(user, sms_tool=_sms),
            Tools.CALL_TOOL: UserCallAdapter(user, call_tool=_call),
            Tools.BUSINESS_CALL_TOOL: UserBusinessCallAdapter(user, call_tool=_call),
            Tools.CALENDAR_TOOL: UserCalendarAdapter(user),
            Tools.GMAIL_TOOL: UserGmailAdapter(user),
        }
    else:
        tool_registry = {Tools.SMS_TOOL: _sms, Tools.CALL_TOOL: _call}

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
