# handles incoming sms from twilio
# POST /webhooks/sms - twilio calls this when someone texts G
# validates HMAC, routes through claude, fires the reply via SMSTool, returns empty TwiML

from fastapi import APIRouter, HTTPException, Request, Response

from adapters.communication.sms_tool import SMSTool
from adapters.llm.claude_adapter import ClaudeAdapter
from config import TWILIO_AUTH_TOKEN
from middleware.twilio_signature import validate_twilio_signature

router = APIRouter()

# Module-level singletons — reuse HTTP connection pools across requests.
_llm = ClaudeAdapter()
_sms = SMSTool()


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

Tools you can use: sms_tool, calendar_tool, gmail_tool, call_tool"""
# [GenAI Use] LLM Response End
# [GenAI Use] Reflection: shape matches the voice prompt deliberately so when
# elliot's orchestrator takes over, it can route both channels through the
# same task-planning JSON contract. the only difference is response_message
# being short for SMS instead of "short for voice" — same idea, different
# medium. dropped conversation history for now (SMS doesn't track that yet
# the way voice does by CallSid; can add a memory keyed on From number later).


@router.post("/webhooks/sms")
async def inbound_sms(request: Request) -> Response:
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

    # TODO(jonathan): look up the user by phone once the users table is queryable.
    # user = user_service.find_by_phone(db, from_number)
    # if not user: send onboarding link via SMSTool and return

    # TODO: persist inbound message + enqueue plan_steps for celery to execute.
    # Synchronous LLM call here is a deviation from "validate → enqueue → return
    # fast"; once elliot's orchestrator + celery exist, this becomes a queue push.
    try:
        plan = _llm.handle(body, SMS_SYSTEM_PROMPT)
        reply = (plan.get("response_message") or "").strip() or "Got it."
    except Exception as exc:
        print(f"[sms llm error] {type(exc).__name__}: {exc}", flush=True)
        reply = "Sorry, I had trouble with that. Try again?"

    # Fire the reply via SMSTool. Wrap so an outbound failure (e.g. A2P not yet
    # approved) doesn't 500 the webhook — twilio just retries on 5xx.
    try:
        _sms.send(to=from_number, body=reply)
    except Exception as exc:
        print(f"[sms send error] {type(exc).__name__}: {exc}", flush=True)

    # Architecture: webhook stays thin, return empty TwiML 200.
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response/>',
        media_type="application/xml",
    )
