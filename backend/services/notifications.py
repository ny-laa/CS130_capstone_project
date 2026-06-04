# proactive outbound to a registered user.
# notify_user is the primitive the scheduler (morning digest), reminder
# follow-ups, and any other "G reaches out first" path will call. webhook
# replies stay on dispatch.run_plan -- those are inside an active conversation
# and don't gate on quiet hours.

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from adapters.communication.call_tool import OutboundCallTool
from adapters.communication.sms_tool import SMSTool
from models.user import User
from services.message_service import log_message


# Module-level singletons -- same pattern as webhooks/debug. Twilio HTTP
# clients reuse their connection pool across requests.
_sms = SMSTool()
_call = OutboundCallTool()


def _now_hhmm() -> str:
    # TODO: per-user timezone. server local time for now -- fine while every
    # demo user is in LA.
    return datetime.now().strftime("%H:%M")


def _in_quiet_hours(blocked_windows: Any, now_hhmm: str | None = None) -> bool:
    """True if `now` falls inside any window in `blocked_windows`.

    blocked_windows shape from the preferences form is
    [{"start_time": "HH:MM", "end_time": "HH:MM"}, ...]. We do plain string
    compare because HH:MM is lexicographically ordered the same as time-of-day.
    Cross-midnight windows (e.g. 22:00 -> 07:00) are handled by the OR branch.
    """
    if not blocked_windows:
        return False
    now = now_hhmm or _now_hhmm()
    for window in blocked_windows:
        start = window.get("start_time")
        end = window.get("end_time")
        if not start or not end:
            continue
        if start <= end:
            if start <= now < end:
                return True
        else:
            # wraps midnight
            if now >= start or now < end:
                return True
    return False


def notify_user(
    db: Session,
    user: User,
    message: str,
    channel: str | None = None,
    force: bool = False,
    task_id: Any = None,
) -> dict:
    """Send `message` to `user` proactively. Returns a status dict.

    channel: "sms" | "call" | None. None -> user.preferred_channel -> "sms".
    force:   bypass the quiet-hours check (use for emergencies / explicit user
             ask, not for routine digests).
    task_id: optional Task UUID. when set, the outbound message row is linked
             back to the task so History / Tasks can cross-reference.

    The outbound row is logged regardless of whether Twilio actually delivers
    -- A2P verification is still pending and we want the UI to replay the
    intended message either way.
    """
    if not message or not message.strip():
        raise ValueError("notify_user: message cannot be empty")

    resolved_channel = channel
    if resolved_channel is None and user.preferred_channel is not None:
        resolved_channel = user.preferred_channel.value
    if resolved_channel is None:
        resolved_channel = "sms"

    if not force and _in_quiet_hours(user.blocked_windows):
        return {"status": "skipped_quiet_hours", "channel": resolved_channel}

    log_channel = "voice" if resolved_channel == "call" else "sms"
    send_status = "ok"
    send_error: str | None = None
    sid: str | None = None

    try:
        if resolved_channel == "call":
            sid = _call.place_call(to=user.phone_number, message=message)
        else:
            sid = _sms.send(to=user.phone_number, body=message)
    except Exception as exc:
        send_status = "error"
        send_error = f"{type(exc).__name__}: {exc}"
        print(f"[notify_user send error] {send_error}", flush=True)

    # Log outbound regardless of send success -- a2p-rejected sends still
    # show in the UI so we can demo end-to-end while twilio verification is pending.
    try:
        log_message(
            db,
            content=message,
            direction="outbound",
            channel=log_channel,
            user_id=user.id,
            task_id=task_id,
        )
    except Exception as exc:
        print(f"[notify_user log error] {type(exc).__name__}: {exc}", flush=True)

    return {
        "status": send_status,
        "channel": resolved_channel,
        "sid": sid,
        "error": send_error,
    }
