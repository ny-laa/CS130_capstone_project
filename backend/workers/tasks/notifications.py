# celery task that runs notify_user. dispatch hands off here via
# apply_async(eta=dt) when claude emits a scheduled sms_tool / call_tool
# plan step ("call me at 6:55pm" -> scheduled_at=ISO).
#
# the task opens its own session_scope because the request's db session
# is long-closed by the time the worker fires.

from uuid import UUID

from database import session_scope
from models.datatypes import TaskStatus
from services.notifications import notify_user
from services.task_service import (
    mark_task_complete,
    mark_task_failed,
    update_task_status,
)
from services.user_service import get_user_by_id
from workers.celery_app import app


@app.task(name="notify_user")
def notify_user_task(
    user_id_str: str,
    message: str,
    channel: str,
    task_id_str: str | None = None,
) -> dict:
    """Fire a scheduled notification.

    user_id / task_id arrive as strings because celery's json serializer
    doesn't speak UUID; we re-parse here. force=True because the user
    explicitly scheduled this turn -- quiet hours don't apply to "remind
    me at 6:55pm specifically".

    When task_id is given, this task owns its lifecycle:
        PENDING -> IN_PROGRESS on entry
        COMPLETED on success
        FAILED on error (notify_user returns status='error' or user gone)

    The outbound message row gets linked back to the task via
    notify_user(task_id=...), so the History page can be filtered to a
    specific task and the Tasks dashboard can stop showing this row
    (the COMPLETED row is now represented by the message in History).
    """
    user_id = UUID(user_id_str)
    task_uuid = UUID(task_id_str) if task_id_str else None

    with session_scope() as db:
        user = get_user_by_id(db, user_id)
        if user is None:
            print(f"[notify_user_task] user {user_id} gone, dropping", flush=True)
            if task_uuid is not None:
                # bookkeeping failure shouldn't block return; row may have
                # been deleted alongside the user.
                try:
                    mark_task_failed(db, task_uuid)
                except Exception:
                    pass
            return {"status": "error", "error": "user not found"}

        if task_uuid is not None:
            try:
                update_task_status(db, task_uuid, TaskStatus.IN_PROGRESS)
            except Exception as exc:
                print(
                    f"[notify_user_task in_progress] {type(exc).__name__}: {exc}",
                    flush=True,
                )

        result = notify_user(
            db,
            user,
            message=message,
            channel=channel,
            force=True,
            task_id=task_uuid,
        )

        if task_uuid is not None:
            try:
                if result.get("status") == "ok":
                    mark_task_complete(db, task_uuid)
                else:
                    mark_task_failed(db, task_uuid)
            except Exception as exc:
                print(
                    f"[notify_user_task close] {type(exc).__name__}: {exc}",
                    flush=True,
                )

        return result
