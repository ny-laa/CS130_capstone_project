# celery task that runs notify_user. dispatch hands off here via
# apply_async(countdown=N) when claude emits a delayed sms_tool / call_tool
# plan step ("call me in 30 minutes" -> delay_seconds=1800).
#
# the task opens its own session_scope because the request's db session is
# long-closed by the time the worker fires.

from uuid import UUID

from database import session_scope
from services.notifications import notify_user
from services.user_service import get_user_by_id
from workers.celery_app import app


@app.task(name="notify_user")
def notify_user_task(user_id_str: str, message: str, channel: str) -> dict:
    """user_id arrives as a string -- celery's json serializer doesn't speak
    UUID natively, so we re-parse here. force=True because the user explicitly
    scheduled this; quiet hours aren't relevant for "call me at 6:05pm
    specifically"."""
    user_id = UUID(user_id_str)
    with session_scope() as db:
        user = get_user_by_id(db, user_id)
        if user is None:
            print(f"[notify_user_task] user {user_id} gone, dropping", flush=True)
            return {"status": "error", "error": "user not found"}
        return notify_user(db, user, message=message, channel=channel, force=True)
