# Generic celery task that runs a single plan_step at its scheduled eta.
# dispatch.run_plan hands business_call_tool (and any future schedulable
# non-notify tool) over here via apply_async(eta=).
#
# notify_user_task already exists for sms_tool/call_tool TO the user --
# it's tied to channel routing + quiet-hours + outbound logging through
# notify_user(). This task is for everything else: business calls,
# eventually scheduled calendar ops, etc.
#
# It owns the parent Task row's lifecycle:
#   PENDING  -> IN_PROGRESS on entry
#   COMPLETED on success
#   FAILED on exception or non-ok adapter result

from uuid import UUID

from database import session_scope
from models.datatypes import TaskStatus
from services.plan_step_executor import execute_step
from services.task_service import (
    mark_task_complete,
    mark_task_failed,
    update_task_status,
)
from services.user_service import get_user_by_id
from workers.celery_app import app


@app.task(name="run_plan_step")
def run_plan_step_task(
    user_id_str: str,
    step: dict,
    task_id_str: str | None = None,
) -> dict:
    user_id = UUID(user_id_str)
    task_uuid = UUID(task_id_str) if task_id_str else None

    with session_scope() as db:
        user = get_user_by_id(db, user_id)
        if user is None:
            print(f"[run_plan_step_task] user {user_id} gone, dropping", flush=True)
            if task_uuid is not None:
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
                    f"[run_plan_step_task in_progress] {type(exc).__name__}: {exc}",
                    flush=True,
                )

        try:
            result = execute_step(db, user, step)
        except Exception as exc:
            print(
                f"[run_plan_step_task execute] {type(exc).__name__}: {exc}",
                flush=True,
            )
            if task_uuid is not None:
                try:
                    mark_task_failed(db, task_uuid)
                except Exception:
                    pass
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

        if task_uuid is not None:
            try:
                if result.get("status") == "ok":
                    mark_task_complete(db, task_uuid)
                else:
                    mark_task_failed(db, task_uuid)
            except Exception as exc:
                print(
                    f"[run_plan_step_task close] {type(exc).__name__}: {exc}",
                    flush=True,
                )

        return result
