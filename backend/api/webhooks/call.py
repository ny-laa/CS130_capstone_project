# handles inbound voice calls from twilio
# POST /webhooks/call - greets the caller and gathers speech
# POST /webhooks/call/transcript - receives the transcription and replies
# eventually this will stream audio to deepgram for real-time STT; for now we
# use twilio's built-in <Gather input="speech"> so we can demo end-to-end.

from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from adapters.communication.sms_tool import SMSTool
from adapters.llm.claude_adapter import ClaudeAdapter
from config import TWILIO_AUTH_TOKEN
from database import get_db
from middleware.twilio_signature import validate_twilio_signature
from models.user import User
from services import dispatch
from services.message_service import log_message
from services.user_service import get_user_by_phone

router = APIRouter()

# Module-level singletons
_llm = ClaudeAdapter()
_sms = SMSTool()


def _user_context(user: User) -> dict:
    """Sanitized user view we pass to claude. NEVER include calendar_token /
    gmail_token here — those go to tool adapters at dispatch time."""
    return {
        "user_id": str(user.id),
        "email": user.email,
        "comm_style": user.comm_style.value if user.comm_style else None,
        "preferred_channel": (
            user.preferred_channel.value if user.preferred_channel else None
        ),
    }


ONBOARDING_VOICE_MESSAGE = (
    "Hi! It looks like you don't have a G account yet. "
    "Please sign up at our registration page first. Goodbye."
)

# [GenAI Use] Prompt: "Add multi-turn conversation memory to my Twilio voice
# webhook in /webhooks/call/transcript. Constraints: (1) keep using the existing
# ClaudeAdapter, do not bypass it; (2) thread conversation history through the
# adapter's context parameter; (3) key conversations by Twilio's CallSid so
# concurrent calls stay isolated; (4) write a voice-flavored system prompt that
# asks for the same JSON task-planning schema the adapter already expects, with
# a short response_message because it will be spoken aloud; (5) detect goodbye
# keywords ('goodbye', 'bye bye', 'talk later', etc.) as a quick check that
# short-circuits the LLM call and hangs up cleanly."
# [GenAI Use] LLM Response Start

# In-memory conversation history keyed by Twilio CallSid. Wiped on server
# restart; swap to a Message-table query once the DB lands.
_conversations: dict[str, list[dict]] = {}


VOICE_SYSTEM_PROMPT = """You are G, an AI personal secretary helping a parent on a phone call.
Your response_message will be spoken back via text-to-speech, so keep it under two short sentences. No markdown, no emojis.

Respond with a JSON object only, no extra text:
{
    "task_type": "<one of: reminder, calendar_update, information_request, morning_digest, smalltalk>",
    "description": "<short summary of what the parent is asking for>",
    "plan_steps": [
        {"tool": "<tool name>", "params": {}, "status": "PENDING"}
    ],
    "response_message": "<friendly short reply, will be spoken aloud>"
}

Tools you can use: sms_tool, calendar_tool, gmail_tool, call_tool

If prior conversation history is present in the context, use it to maintain
continuity (e.g. "make it 3pm" refers to whatever event was just discussed)."""


def _is_goodbye(text: str) -> bool:
    """Quick keyword check — saves an LLM call when the user clearly wants to hang up."""
    lower = text.lower().strip()
    return any(p in lower for p in ["goodbye", "bye bye", "talk later", "that's all", "see ya"])


def _plan(call_sid: str, user_text: str, user_ctx: dict | None = None) -> dict:
    """Append the user turn to history, call the adapter, append the reply.

    Returns the full plan dict (task_type, plan_steps, response_message) so
    the caller can dispatch tool calls + speak the response.
    """
    history = _conversations.setdefault(call_sid, [])
    context: dict = {}
    if history:
        context["history"] = list(history)
    if user_ctx:
        context["user"] = user_ctx
    result = _llm.handle(
        user_text,
        VOICE_SYSTEM_PROMPT,
        context=context or None,
    )
    reply = (result.get("response_message") or "").strip() or "Got it."
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply})
    return result
# [GenAI Use] LLM Response End
# [GenAI Use] Reflection: I tested this end-to-end with a mocked adapter and
# confirmed turn 1 of a call passes context=None since there's no history
# yet, turn 2 correctly threads the prior user+assistant turns through
# context, two concurrent calls with different CallSids keep their own
# state and don't cross-contaminate, 'goodbye' short-circuits without an
# LLM call and clears the history entry


async def _params_or_403(request: Request) -> dict[str, str]:
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    if not validate_twilio_signature(
        TWILIO_AUTH_TOKEN,
        request.headers.get("X-Twilio-Signature"),
        str(request.url),
        params,
    ):
        raise HTTPException(status_code=403, detail="invalid twilio signature")
    return params


@router.post("/webhooks/call")
async def inbound_call(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    params = await _params_or_403(request)
    from_number = params.get("From", "")

    # Unregistered numbers get bounced at the greeting — no point starting a
    # conversation if claude can't identify them or touch their calendar.
    if from_number:
        user = get_user_by_phone(db, from_number)
        if user is None:
            twiml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f"<Response><Say>{escape(ONBOARDING_VOICE_MESSAGE)}</Say></Response>"
            )
            return Response(content=twiml, media_type="application/xml")

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        '<Gather input="speech" action="/webhooks/call/transcript"'
        ' method="POST" speechTimeout="auto">'
        "<Say>Hi, this is G. What can I help you with?</Say>"
        "</Gather>"
        "<Say>I didn't catch that. Goodbye.</Say>"
        "</Response>"
    )
    return Response(content=twiml, media_type="application/xml")


@router.post("/webhooks/call/transcript")
async def call_transcript(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    params = await _params_or_403(request)
    call_sid = params.get("CallSid", "unknown")
    from_number = params.get("From", "")
    speech_raw = params.get("SpeechResult", "").strip()

    # Silence ends the call gracefully and clears history.
    if not speech_raw:
        _conversations.pop(call_sid, None)
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Say>I didn't catch that. Goodbye.</Say></Response>"
        )
        return Response(content=twiml, media_type="application/xml")

    # Quickly end call when the caller clearly wants to hang up.
    if _is_goodbye(speech_raw):
        _conversations.pop(call_sid, None)
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Say>Goodbye.</Say></Response>"
        )
        return Response(content=twiml, media_type="application/xml")

    # Look up the caller. Unregistered numbers shouldn't reach claude —
    # they get bounced to onboarding and the call ends.
    user = get_user_by_phone(db, from_number) if from_number else None
    if user is None:
        _conversations.pop(call_sid, None)
        twiml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Say>{escape(ONBOARDING_VOICE_MESSAGE)}</Say></Response>"
        )
        return Response(content=twiml, media_type="application/xml")

    # Log inbound voice so the UI can replay the conversation later.
    try:
        log_message(db, content=speech_raw, direction="inbound", channel="voice", user_id=user.id)
    except Exception as exc:
        print(f"[voice inbound log error] {type(exc).__name__}: {exc}", flush=True)

    # Get the full plan from claude, then dispatch any tool calls before
    # speaking the response. Synchronous on the webhook thread; becomes a
    # celery push once that's wired.
    try:
        plan = _plan(call_sid, speech_raw, user_ctx=_user_context(user))
        reply = (plan.get("response_message") or "").strip() or "Got it."
    except Exception as exc:
        print(f"[llm error] {type(exc).__name__}: {exc}", flush=True)
        plan = {}
        reply = "Sorry, I had trouble with that. Could you try again?"

    # Log outbound voice (what gets spoken via TwiML below) regardless of
    # downstream outcomes -- it's what G said, the UI needs it.
    try:
        log_message(db, content=reply, direction="outbound", channel="voice", user_id=user.id)
    except Exception as exc:
        print(f"[voice outbound log error] {type(exc).__name__}: {exc}", flush=True)

    # Run any plan_steps claude generated (calendar/gmail updates etc).
    # Tokens get injected from `user` inside dispatch -- never via the LLM.
    # Dispatch errors are swallowed here so the call doesn't die mid-flight.
    if plan.get("plan_steps"):
        try:
            dispatch.run_plan(plan, user)
        except Exception as exc:
            print(f"[dispatch error] {type(exc).__name__}: {exc}", flush=True)

    # Fire a confirmation SMS so the caller has a written record of what G
    # heard / agreed to do. Closes the "call → G texts you back" loop for #11.
    # Wrapped so an outbound failure (A2P not yet approved, etc.) doesn't
    # break the call.
    try:
        _sms.send(to=from_number, body=reply)
    except Exception as exc:
        print(f"[sms confirmation error] {type(exc).__name__}: {exc}", flush=True)

    # Log outbound SMS confirmation regardless of send success -- a2p-rejected
    # sends still show in the UI so we can demo end-to-end while pending.
    try:
        log_message(db, content=reply, direction="outbound", channel="sms", user_id=user.id)
    except Exception as exc:
        print(f"[sms confirmation log error] {type(exc).__name__}: {exc}", flush=True)

    # Speak the reply while immediately listening for the parent's next utterance.
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        '<Gather input="speech" action="/webhooks/call/transcript"'
        ' method="POST" speechTimeout="auto">'
        f"<Say>{escape(reply)}</Say>"
        "</Gather>"
        "<Say>Goodbye.</Say>"
        "</Response>"
    )
    return Response(content=twiml, media_type="application/xml")
