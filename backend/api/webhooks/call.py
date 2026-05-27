# handles inbound voice calls from twilio
# POST /webhooks/call - greets the caller and gathers speech
# POST /webhooks/call/transcript - receives the transcription and replies
# eventually this will stream audio to deepgram for real-time STT; for now we
# use twilio's built-in <Gather input="speech"> so we can demo end-to-end.

from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Request, Response

from adapters.communication.sms_tool import SMSTool
from adapters.llm.claude_adapter import ClaudeAdapter
from config import TWILIO_AUTH_TOKEN
from middleware.twilio_signature import validate_twilio_signature

router = APIRouter()

# Module-level singletons — reuse HTTP connection pools across requests.
_llm = ClaudeAdapter()
_sms = SMSTool()

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


def _chat(call_sid: str, user_text: str) -> str:
    """Append the user turn to history, route through the adapter, append the reply.

    Same adapter contract the orchestrator will plug into later — when it lands,
    this helper gets replaced by an orchestrator call. Voice plumbing stays identical.
    """
    history = _conversations.setdefault(call_sid, [])
    # Pass a snapshot so later appends in this function don't mutate what the
    # adapter (or anything it captured) is holding.
    result = _llm.handle(
        user_text,
        VOICE_SYSTEM_PROMPT,
        context={"history": list(history)} if history else None,
    )
    reply = (result.get("response_message") or "").strip() or "Got it."
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": reply})
    return reply
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
async def inbound_call(request: Request) -> Response:
    await _params_or_403(request)
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
async def call_transcript(request: Request) -> Response:
    params = await _params_or_403(request)
    call_sid = params.get("CallSid", "unknown")
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

    # TODO: persist transcript + enqueue plan_steps for celery to execute.
    # Synchronous LLM call on the webhook thread is a deviation from the
    # architecture's "validate → enqueue → return fast" rule; replace with
    # an async outbound reply once the orchestrator + celery exist.
    try:
        reply = _chat(call_sid, speech_raw)
    except Exception as exc:
        print(f"[llm error] {type(exc).__name__}: {exc}", flush=True)
        reply = "Sorry, I had trouble with that. Could you try again?"

    # Fire a confirmation SMS so the caller has a written record of what G
    # heard / agreed to do. Closes the "call → G texts you back" loop for #11.
    # Wrapped so an outbound failure (A2P not yet approved, no From=, etc.)
    # doesn't break the call.
    from_number = params.get("From", "")
    if from_number:
        try:
            _sms.send(to=from_number, body=reply)
        except Exception as exc:
            print(f"[sms confirmation error] {type(exc).__name__}: {exc}", flush=True)

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
