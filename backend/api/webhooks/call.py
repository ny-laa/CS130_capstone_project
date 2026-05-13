# handles inbound voice calls from twilio
# POST /webhooks/call - greets the caller and gathers speech
# POST /webhooks/call/transcript - receives the transcription and replies
# eventually this will stream audio to deepgram for real-time STT; for now we
# use twilio's built-in <Gather input="speech"> so we can demo end-to-end.

from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Request, Response

from config import TWILIO_AUTH_TOKEN
from middleware.twilio_signature import validate_twilio_signature

router = APIRouter()


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
    speech = escape(params.get("SpeechResult", ""))
    # TODO: persist transcript + enqueue celery task. Canned echo is a demo
    # affordance; the real reply will come from the orchestrator once it exists.
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Say>You said: {speech}. Got it. Goodbye.</Say>"
        "</Response>"
    )
    return Response(content=twiml, media_type="application/xml")
