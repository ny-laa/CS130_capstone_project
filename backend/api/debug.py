# debug endpoints for manually triggering outbound tools
# mounted only when DEBUG=true so they can't fire in prod by accident

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from adapters.communication.call_tool import OutboundCallTool
from adapters.communication.sms_tool import SMSTool


router = APIRouter(prefix="/debug")

# One instance per process — same pattern as the webhook routes.
_call_tool = OutboundCallTool()
_sms_tool = SMSTool()


class CallRequest(BaseModel):
    to: str
    message: str


class SMSRequest(BaseModel):
    to: str
    body: str


@router.post("/call")
async def debug_call(req: CallRequest):
    """Manually place an outbound call. The recipient hears `message`, then G
    listens — anything they say gets posted to /webhooks/call/transcript and
    routed through Claude (same back-and-forth as inbound)."""
    public_base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if not public_base:
        raise HTTPException(
            status_code=500,
            detail="PUBLIC_BASE_URL not set in .env — Twilio needs an absolute URL "
            "to POST the recipient's response to. Set it to your current ngrok URL.",
        )
    callback_url = f"{public_base}/webhooks/call/transcript"
    try:
        sid = _call_tool.place_call(
            to=req.to,
            message=req.message,
            callback_url=callback_url,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"{type(exc).__name__}: {exc}")
    return {"status": "called", "sid": sid}


@router.post("/sms")
async def debug_sms(req: SMSRequest):
    """Manually send an outbound SMS. Lets us test SMSTool before the
    orchestrator and scheduler exist."""
    try:
        sid = _sms_tool.send(to=req.to, body=req.body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"{type(exc).__name__}: {exc}")
    return {"status": "sent", "sid": sid}
