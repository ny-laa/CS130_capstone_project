# handles incoming sms from twilio
# POST /webhooks/sms - twilio calls this when someone texts G
# validates HMAC, routes through claude, fires the reply via SMSTool, returns empty TwiML

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from adapters.communication.call_tool import OutboundCallTool
from adapters.communication.sms_tool import SMSTool
from adapters.communication.user_call_adapter import UserCallAdapter
from adapters.communication.user_sms_adapter import UserSMSAdapter
from adapters.google.user_calendar_adapter import UserCalendarAdapter
from adapters.llm.claude_adapter import ClaudeAdapter
from config import TWILIO_AUTH_TOKEN
from database import get_db
from middleware.twilio_signature import validate_twilio_signature
from models.datatypes import TaskStatus, Tools
from orchestrator.orchestrator import GOrchestrator
from orchestrator.task_planner import PlanStep, StructuredTaskPlan
from orchestrator.task_planner import Task as InMemoryTask
from services import task_service
from services.message_service import log_message
from services.user_service import get_user_by_phone
from services.user_context_service import build_user_context
from workers.task_runner import TaskRunner


router = APIRouter()

# Module-level singletons — reuse HTTP connection pools across requests.
_llm = ClaudeAdapter()
_sms = SMSTool()
_call = OutboundCallTool()
_orch = GOrchestrator()


# TODO: swap with the deployed signup URL once the frontend ships.
ONBOARDING_REPLY = (
    "Hi! You don't have a G account yet. Sign up at our registration page "
    "to get started. Reply HELP for support."
)


# [GenAI Use] Prompt: "write a sms-flavored system prompt for the existing
# ClaudeAdapter that asks for the same JSON task-planning schema we use for
# voice, but tells claude (a) the response_message will go out as an SMS so
# keep it short, no markdown, and (b) to use prior conversation context for
# follow-ups when present. Mirror the voice prompt shape so the orchestrator
# can swap in cleanly later."
# [GenAI Use] LLM Response Start
SMS_SYSTEM_PROMPT = """You are G, an AI personal secretary helping a parent over SMS.
Your response_message will be sent back as a text message, so keep it short (under 160 characters when possible) and avoid markdown or emoji.

Respond with a JSON object only, no extra text:
{
    "task_type": "<one of: reminder, calendar_update, information_request, morning_digest, smalltalk>",
    "description": "<short summary of what the parent is asking for>",
    "plan_steps": [
        {"tool": "<tool name>", "params": {}, "status": "PENDING"}
    ],
    "response_message": "<short reply, will be sent as SMS>"
}

Tools you can use: sms_tool, calendar_tool, gmail_tool, call_tool

The current time is provided in the context as `current_time_iso` (ISO 8601 with timezone offset). For sms_tool / call_tool, when the parent asks you to reach out *later* -- either an absolute time ("at 5pm", "tomorrow at 8am") OR a relative duration ("in 30 minutes", "in 2 hours") -- set `params.scheduled_at` to the absolute ISO 8601 timestamp (same timezone as `current_time_iso`) when the notification should fire. Examples: if current_time_iso is "2026-05-31T18:48:00-07:00" and the parent says "in 2 minutes", scheduled_at is "2026-05-31T18:50:00-07:00". If they say "at 6:55", it's "2026-05-31T18:55:00-07:00". Omit `scheduled_at` when the parent wants the action immediately."""
# [GenAI Use] LLM Response End
# [GenAI Use] Reflection: shape matches the voice prompt deliberately so when
# elliot's orchestrator takes over, it can route both channels through the
# same task-planning JSON contract. the only difference is response_message
# being short for SMS instead of "short for voice" — same idea, different
# medium. dropped conversation history for now (SMS doesn't track that yet
# the way voice does by CallSid; can add a memory keyed on From number later).


@router.post("/webhooks/sms")
async def inbound_sms(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}

    if not validate_twilio_signature(
        TWILIO_AUTH_TOKEN,
        request.headers.get("X-Twilio-Signature"),
        str(request.url),
        params,
    ):
        raise HTTPException(status_code=403, detail="invalid twilio signature")

    from_number = params.get("From", "")
    body = params.get("Body", "").strip()

    # Nothing to reply to — just ack so twilio doesn't retry.
    if not body or not from_number:
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response/>',
            media_type="application/xml",
        )

    # Look up the user. Unregistered numbers get an onboarding nudge instead
    # of being routed through Claude (no user context, no calendar/gmail token).
    user = get_user_by_phone(db, from_number)
    if user is None:
        try:
            _sms.send(to=from_number, body=ONBOARDING_REPLY)
        except Exception as exc:
            print(f"[sms onboarding send error] {type(exc).__name__}: {exc}", flush=True)
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response/>',
            media_type="application/xml",
        )

    # Log inbound so the UI can replay the conversation later.
    try:
        log_message(db, content=body, direction="inbound", channel="sms", user_id=user.id)
    except Exception as exc:
        print(f"[sms inbound log error] {type(exc).__name__}: {exc}", flush=True)

    # Synchronous LLM call here is a deviation from "validate → enqueue →
    # return fast"; becomes a queue push once celery is wired.
    try:
        user_context = build_user_context(db, user.id)
        user_context["current_time_iso"] = datetime.now().astimezone().isoformat()

        plan = _llm.handle(
            body,
            SMS_SYSTEM_PROMPT,
            context=user_context,
        )
        reply = (plan.get("response_message") or "").strip() or "Got it."
    except Exception as exc:
        print(f"[sms llm error] {type(exc).__name__}: {exc}", flush=True)
        plan = {}
        reply = "Sorry, I had trouble with that. Try again?"

    # If any step has scheduled_at, route via dispatch.run_plan -- it handles
    # task row creation, dedup of duplicate ETAs, and Celery enqueue with
    # eta=. TaskRunner doesn't know about scheduling and would fire the
    # SMS/call immediately, which defeats "remind me at 2:30pm".
    plan_steps_raw = plan.get("plan_steps") or []
    has_scheduled_step = any(
        isinstance(s, dict) and (s.get("params") or {}).get("scheduled_at")
        for s in plan_steps_raw
    )

    escalated = False
    db_task = None
    if has_scheduled_step:
        from services.dispatch import run_plan as dispatch_run_plan
        try:
            dispatch_run_plan(plan, user, db)
        except Exception as exc:
            print(f"[sms dispatch error] {type(exc).__name__}: {exc}", flush=True)
    else:
        # save task so approve/deny endpoints can find it by id
        if plan.get("task_type") and plan.get("description"):
            try:
                db_task = task_service.create_task(
                    db,
                    user_id=user.id,
                    task_type=plan["task_type"],
                    description=plan["description"],
                    plan_steps=plan_steps_raw,
                )
            except Exception as exc:
                print(f"[sms persist error] {type(exc).__name__}: {exc}", flush=True)

        # run steps through TaskRunner so calendar conflicts pause for parent approval
        if plan_steps_raw and db_task is not None:
            try:
                steps = [
                    PlanStep(tool=s["tool"], params=s.get("params", {}), status=TaskStatus.PENDING)
                    for s in plan_steps_raw
                ]
                plan_obj = StructuredTaskPlan(
                    task_type=plan["task_type"],
                    description=plan["description"],
                    plan_steps=steps,
                    response_message=reply,
                )
                in_mem = InMemoryTask(
                    id=db_task.id,
                    user_id=user.id,
                    status=TaskStatus.PENDING,
                    task_plan=plan_obj,
                    escalation_deadline=None,
                    created_at=None,
                    updated_at=None,
                )
                # Comm tools are per-user so the adapter injects `to=user.phone_number`
                # before hitting Twilio -- claude isn't given the user's phone, so
                # the base tools KeyError on params["to"]. CALL_TOOL is registered
                # alongside SMS even on the SMS surface because claude can pick
                # call_tool when the user texts "call me at 6pm" or has
                # preferred_channel="call".
                tool_registry = {
                    Tools.CALENDAR_TOOL: UserCalendarAdapter(user),
                    Tools.SMS_TOOL: UserSMSAdapter(user, sms_tool=_sms),
                    Tools.CALL_TOOL: UserCallAdapter(user, call_tool=_call),
                }
                TaskRunner(tool_registry).run(in_mem)
                task_service.update_task_status(db, db_task.id, in_mem.status)
                task_service.update_plan_steps(db, db_task.id, in_mem.task_plan.plan_steps)
                if in_mem.status == TaskStatus.ESCALATION_PENDING:
                    _orch.request_escalation_approval(in_mem, _sms, from_number)
                    escalated = True
            except Exception as exc:
                print(f"[runner error] {type(exc).__name__}: {exc}", flush=True)

    if not escalated:
        try:
            _sms.send(to=from_number, body=reply)
        except Exception as exc:
            print(f"[sms send error] {type(exc).__name__}: {exc}", flush=True)
        try:
            log_message(db, content=reply, direction="outbound", channel="sms", user_id=user.id)
        except Exception as exc:
            print(f"[sms outbound log error] {type(exc).__name__}: {exc}", flush=True)

    # Architecture: webhook stays thin, return empty TwiML 200.
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response/>',
        media_type="application/xml",
    )
