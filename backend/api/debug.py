# debug endpoints for manually triggering outbound tools
# mounted only when DEBUG=true so they can't fire in prod by accident

import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from adapters.communication.call_tool import OutboundCallTool
from adapters.communication.sms_tool import SMSTool
from database import get_db
from services.notifications import notify_user
from services.user_service import get_user_by_id


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


class NotifyRequest(BaseModel):
    message: str
    channel: str | None = None  # "sms" | "call" -- defaults to user.preferred_channel
    force: bool = False  # bypass quiet-hours check


@router.post("/notify/{user_id}")
async def debug_notify(
    user_id: UUID, req: NotifyRequest, db: Session = Depends(get_db)
):
    """Fire a proactive notification at a registered user. Mirrors the path
    the scheduler will use once celery beat is wired -- channel routing,
    quiet hours, outbound logging all go through notify_user."""
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    try:
        return notify_user(
            db, user, message=req.message, channel=req.channel, force=req.force
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
