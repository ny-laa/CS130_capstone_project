# handles incoming sms from twilio
# POST /webhooks/sms - twilio calls this when someone texts G
# validates HMAC, routes through claude, fires the reply via SMSTool, returns empty TwiML

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from adapters.communication.sms_tool import SMSTool
from adapters.llm.claude_adapter import ClaudeAdapter
from config import TWILIO_AUTH_TOKEN
from database import get_db
from middleware.twilio_signature import validate_twilio_signature
from services import dispatch, task_service
from services.message_service import log_message
from services.user_service import get_user_by_phone
from services.user_context_service import build_user_context


router = APIRouter()

# Module-level singletons — reuse HTTP connection pools across requests.
_llm = ClaudeAdapter()
_sms = SMSTool()


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

    # save task so the frontend and approve/deny endpoints can look it up by id
    if plan.get("task_type") and plan.get("description"):
        try:
            task_service.create_task(
                db,
                user_id=user.id,
                task_type=plan["task_type"],
                description=plan["description"],
                plan_steps=plan.get("plan_steps", []),
            )
        except Exception as exc:
            print(f"[sms persist error] {type(exc).__name__}: {exc}", flush=True)

    # Run any plan_steps claude generated (calendar/gmail/etc). Tokens get
    # injected from `user` inside dispatch -- never via the LLM. Dispatch
    # errors don't 5xx the webhook (twilio retries on 5xx, we don't want that).
    if plan.get("plan_steps"):
        try:
            dispatch.run_plan(plan, user, db)
        except Exception as exc:
            print(f"[dispatch error] {type(exc).__name__}: {exc}", flush=True)

    # Fire the reply via SMSTool. Wrap so an outbound failure (e.g. A2P not yet
    # approved) doesn't 500 the webhook — twilio just retries on 5xx.
    try:
        _sms.send(to=from_number, body=reply)
    except Exception as exc:
        print(f"[sms send error] {type(exc).__name__}: {exc}", flush=True)

    # Log outbound regardless of send success -- a2p-rejected sends still
    # show in the UI so we can demo end-to-end while twilio verification is pending.
    try:
        log_message(db, content=reply, direction="outbound", channel="sms", user_id=user.id)
    except Exception as exc:
        print(f"[sms outbound log error] {type(exc).__name__}: {exc}", flush=True)

    # Architecture: webhook stays thin, return empty TwiML 200.
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response/>',
        media_type="application/xml",
    )
