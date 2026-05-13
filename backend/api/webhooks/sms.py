# handles incoming sms from twilio
# POST /webhook/sms - twilio calls this when someone texts G
# needs to validate the twilio signature first (see middleware)

from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Request, Response

from config import TWILIO_AUTH_TOKEN
from middleware.twilio_signature import validate_twilio_signature

router = APIRouter()


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

    # TODO: persist message + enqueue celery task. Synchronous echo is a demo
    # affordance — once the orchestrator lands, reply async via outbound SMS
    # and return an empty <Response/> here.
    body = escape(params.get("Body", ""))
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>Got it. You said: {body}</Message></Response>"
    )
    return Response(content=twiml, media_type="application/xml")
