# handles inbound voice calls from twilio
# POST /webhooks/call - greets the caller and gathers speech
# POST /webhooks/call/transcript - receives the transcription and replies
# eventually this will stream audio to deepgram for real-time STT; for now we
# use twilio's built-in <Gather input="speech"> so we can demo end-to-end.

from datetime import datetime
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from adapters.communication.sms_tool import SMSTool
from adapters.llm.claude_adapter import ClaudeAdapter
from config import TWILIO_AUTH_TOKEN
from database import get_db
from middleware.twilio_signature import validate_twilio_signature
from models.user import User
from services import dispatch, outbound_call_state
from services.message_service import log_message
from services.user_service import get_user_by_phone
from services.user_context_service import build_user_context


router = APIRouter()

# Module-level singletons
_llm = ClaudeAdapter()
_sms = SMSTool()


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

Tools you can use: sms_tool, calendar_tool, gmail_tool, call_tool, business_call_tool

`business_call_tool` is used when the parent asks you to phone an external business or person on their behalf (e.g. "call the pizza place and order a large pepperoni"). Params: `to` (business phone number), `goal` (one sentence describing what to accomplish, including order/time/address details), optional `business_name`. Only plan it when you have a phone number to dial; otherwise ask the parent for it.

When to ask a clarifying question FIRST instead of acting:
You're a capable assistant — pause before committing for high-stakes or irreversible actions. If anything material is missing/ambiguous, set task_type="smalltalk", leave plan_steps empty, and use response_message to ask. The parent is ON THE PHONE WITH YOU, so just ask — they'll answer in the next turn.
  - business_call_tool: ALWAYS verify before dialing — confirm the number, the exact goal details, and that the parent wants you to call now.
  - Purchases / paid bookings — confirm amount and merchant.
  - Calendar deletes/updates where the target event isn't obvious — ask which.
Lower-stakes (reminders to the parent themselves, clear personal calendar entries, reading gmail) can proceed without clarification.

If prior conversation history is present in the context, use it to maintain
continuity (e.g. "make it 3pm" refers to whatever event was just discussed).

The current time is provided in the context as `current_time_iso` (ISO 8601
with timezone offset). For sms_tool, call_tool, AND business_call_tool, when
the parent asks you to do the action *later* -- either an absolute time
("at 5pm", "tomorrow at 8am") OR a relative duration ("in 30 minutes", "in 2
hours") -- set `params.scheduled_at` to the absolute ISO 8601 timestamp
(same timezone as `current_time_iso`) when it should fire. Examples: if
current_time_iso is "2026-05-31T18:48:00-07:00" and the parent says "in 2
minutes", scheduled_at is "2026-05-31T18:50:00-07:00". If they say "at 6:55",
it's "2026-05-31T18:55:00-07:00". Omit `scheduled_at` only when the parent
wants the action immediately."""


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
        context.update(user_ctx)
    # tz-aware local server time -- claude resolves relative phrasing ("in 2
    # minutes") and absolute phrasing ("at 6:55") against this
    context["current_time_iso"] = datetime.now().astimezone().isoformat()
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
        plan = _plan(
            call_sid,
            speech_raw,
            user_ctx=build_user_context(db, user.id),
        )
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
            dispatch.run_plan(plan, user, db)
        except Exception as exc:
            print(f"[dispatch error] {type(exc).__name__}: {exc}", flush=True)

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


# --- outbound (G calling a business on behalf of the user) ---------------
#
# Flow:
#   1. Chat/SMS plans a business_call_tool step.
#   2. UserBusinessCallAdapter.place_call dials the business, plays an
#      opening line, and registers state keyed by CallSid.
#   3. Employee speaks. Twilio POSTs the transcript here.
#   4. Claude reads (goal, history, latest transcript) and returns
#      {say, hang_up, summary}. We speak `say` and either Gather again
#      or hang up. On hang_up we SMS the user the summary.

OUTBOUND_SYSTEM_PROMPT = """You are G, an AI personal secretary placing a phone call on behalf of {user_name}. You are talking to an employee at {business_name}.

Your goal on this call: {goal}

The full conversation so far is in the context as `history`. The employee's most recent utterance is the user_text you're given.

How to behave:
- Be polite, conversational, concise. Each `say` is 1-2 short sentences — it will be spoken aloud via TTS, so no markdown / lists / asterisks.
- Drive the goal forward ACROSS MULTIPLE TURNS. Do not state the entire goal in one turn. Your opening line already introduced you; your first reply should actually start working toward the goal (e.g. "Great. I'd like to place a delivery order — do you have a minute?"). Share specifics (items, address, time, etc.) gradually as the employee asks for them, the way a human would on a phone call.
- Wait for the employee to acknowledge or confirm each piece before moving on. Don't dump everything in one breath.
- If asked who you are, say you're G, an AI assistant calling on behalf of {user_name}. If asked for a callback number, give {user_phone}. If you don't know a specific detail (exact payment method, full address, etc.), say you'll have {user_name} follow up directly.

When to hang up (set hang_up=true):
- ONLY after the employee has clearly CONFIRMED the goal is fully completed (e.g. order taken with a price and ETA, appointment booked with a date+time, etc.).
- OR if the employee explicitly cannot help, is closing the call, or the call is clearly stuck.
- Do NOT hang up just because you've stated what you want. Stating intent is not the same as the goal being achieved — the employee has to actually do the thing.

Respond with JSON only:
{
    "say": "<short polite reply, will be spoken aloud>",
    "hang_up": <true ONLY if the employee has confirmed completion or the call cannot continue>,
    "summary": "<one-line summary of the outcome -- only when hang_up is true>"
}"""


def _generic_outbound_error_twiml() -> Response:
    """Last-resort TwiML returned when anything blows up inside the
    outbound transcript handler. Returning 200 with valid TwiML keeps
    twilio from playing its default "application error occurred" message."""
    return Response(
        content=(
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Say>I'm having trouble on my end. I'll have someone follow up. Goodbye.</Say></Response>"
        ),
        media_type="application/xml",
    )


@router.post("/webhooks/call/outbound-transcript")
async def outbound_call_transcript(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Twilio POSTs here each time the business employee finishes speaking
    during an outbound business call. We run claude with the call's goal +
    history and either speak the next line or hang up + SMS the user a
    summary.

    Wrapped in a single broad try/except: anything raising bubbles up to
    twilio as "application error occurred" via a 500 response, which is
    the symptom we keep hitting. Better to log the traceback and play a
    polite hangup line.
    """
    # Signature validation lives outside the try/except deliberately --
    # if a non-twilio caller hits this we want to reject (403), not
    # mask the rejection with a "we had trouble" voice line.
    try:
        params = await _params_or_403(request)
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[outbound sig parse error] {type(exc).__name__}: {exc}", flush=True)
        return _generic_outbound_error_twiml()

    call_sid = params.get("CallSid", "")
    speech_raw = params.get("SpeechResult", "").strip()
    print(
        f"[outbound] sid={call_sid} speech={speech_raw!r:.80}",
        flush=True,
    )

    try:
        state = outbound_call_state.get(call_sid)
        if state is None:
            # No tracked state -- server restarted mid-call, or a stray
            # webhook. Polite hangup beats a 500 to twilio.
            print(f"[outbound] sid={call_sid} no state (restart?) — hanging up", flush=True)
            return Response(
                content=(
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    "<Response><Say>Sorry, I lost track of this call. Goodbye.</Say></Response>"
                ),
                media_type="application/xml",
            )

        # Silence: employee said nothing this turn. Don't hang up yet --
        # prompt them once and gather again.
        if not speech_raw:
            print(f"[outbound] sid={call_sid} empty speech, reprompting", flush=True)
            return Response(
                content=(
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    "<Response>"
                    '<Gather input="speech" action="/webhooks/call/outbound-transcript"'
                    ' method="POST" speechTimeout="auto">'
                    "<Say>Are you still there?</Say>"
                    "</Gather>"
                    "<Say>I'll try again later. Goodbye.</Say>"
                    "</Response>"
                ),
                media_type="application/xml",
            )

        # Append the employee turn to history before claude sees it.
        state.history.append({"role": "user", "content": speech_raw})

        # use replace() instead of format() -- if claude (or the user) wrote
        # the goal with literal `{` `}` characters in it, format() would
        # KeyError trying to interpolate them. replace() is brace-safe.
        prompt = (
            OUTBOUND_SYSTEM_PROMPT
            .replace("{user_name}", state.user_name)
            .replace("{user_phone}", state.user_phone or "no callback number available")
            .replace("{business_name}", state.business_name or "the business")
            .replace("{goal}", state.goal)
        )

        try:
            result = _llm.handle(
                speech_raw,
                prompt,
                context={"history": list(state.history)},
            )
        except Exception as exc:
            print(f"[outbound llm error] {type(exc).__name__}: {exc}", flush=True)
            outbound_call_state.drop(call_sid)
            return _generic_outbound_error_twiml()

        # claude is told to return a JSON dict; defensive against other shapes
        if not isinstance(result, dict):
            print(f"[outbound] sid={call_sid} llm returned non-dict: {type(result).__name__}", flush=True)
            outbound_call_state.drop(call_sid)
            return _generic_outbound_error_twiml()

        say = (result.get("say") or "").strip() or "One moment please."
        hang_up = bool(result.get("hang_up"))
        summary = (result.get("summary") or "").strip()

        state.history.append({"role": "assistant", "content": say})
        print(
            f"[outbound] sid={call_sid} say={say!r:.80} hang_up={hang_up}",
            flush=True,
        )

        if hang_up:
            state.summary = summary or "Call ended."
            # SMS the user with what happened. Best-effort.
            if state.user_phone:
                try:
                    biz = state.business_name or "the business"
                    _sms.send(
                        to=state.user_phone,
                        body=f"Call to {biz} ended. {state.summary}",
                    )
                except Exception as exc:
                    print(f"[outbound summary sms error] {type(exc).__name__}: {exc}", flush=True)
            outbound_call_state.drop(call_sid)

            return Response(
                content=(
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    "<Response>"
                    f"<Say>{escape(say)}</Say>"
                    "</Response>"
                ),
                media_type="application/xml",
            )

        # Continue the conversation: speak the reply and gather the next turn.
        return Response(
            content=(
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<Response>"
                '<Gather input="speech" action="/webhooks/call/outbound-transcript"'
                ' method="POST" speechTimeout="auto">'
                f"<Say>{escape(say)}</Say>"
                "</Gather>"
                "<Say>Sorry, I didn't catch that. Goodbye.</Say>"
                "</Response>"
            ),
            media_type="application/xml",
        )

    except Exception as exc:
        # Catch-all so twilio never sees a 500. The "application error
        # occurred" voice line comes from non-2xx responses; this guarantees
        # we always return clean TwiML even if something below blew up.
        import traceback
        print(
            f"[outbound] sid={call_sid} unhandled exception: "
            f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            flush=True,
        )
        try:
            outbound_call_state.drop(call_sid)
        except Exception:
            pass
        return _generic_outbound_error_twiml()
