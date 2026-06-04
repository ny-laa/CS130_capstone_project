# Periodic scanner that finds PENDING Tasks whose scheduled_at is in the
# past and fires them via notify_user, then marks them COMPLETED/FAILED.
#
# This is the safety net for the celery scheduling path:
#   - Primary path: dispatch.run_plan -> notify_user_task.apply_async(eta=...)
#     -- celery worker fires at the eta.
#   - Fallback (this module): if celery is down, the worker crashed, the
#     server restarted before eta, or apply_async never reached the broker,
#     the scanner catches the dangling PENDING row and fires it here.
#
# Runs as an asyncio task in the FastAPI process (see main.py lifespan).
# Single-process by design -- no distributed locking. If we ever shard
# the API across multiple replicas, switch to an atomic
# `UPDATE ... WHERE status=PENDING RETURNING *` claim before processing.

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from database import session_scope
from models.datatypes import TaskStatus
from models.task import Task as DBTask
from services.notifications import notify_user
from services.task_service import (
    mark_task_complete,
    mark_task_failed,
    update_task_status,
)
from services.user_service import get_user_by_id

logger = logging.getLogger("backend.services.scheduled_task_scanner")

# Tick cadence. Scheduled reminders rarely need sub-minute precision and
# we don't want to hammer the DB. 30s is a reasonable balance.
SCAN_INTERVAL_SECONDS = 30


def _first_step(task: DBTask) -> dict[str, Any] | None:
    steps = task.plan_steps
    if not isinstance(steps, list) or not steps:
        return None
    first = steps[0]
    return first if isinstance(first, dict) else None


def _due_message(task: DBTask, now: datetime) -> tuple[str, str] | None:
    """If this task is a scheduled notification that's due, return
    (message, channel). Otherwise return None and the scanner skips it.

    We only fire tasks whose first plan_step is sms_tool/call_tool with a
    `scheduled_at` <= now. Anything else (calendar steps, immediate sends,
    non-scheduled tasks) is out of scope -- those fire through TaskRunner
    on the request thread, not here.
    """
    step = _first_step(task)
    if step is None:
        return None

    tool = step.get("tool")
    if tool not in ("sms_tool", "call_tool"):
        return None

    params = step.get("params") or {}
    scheduled_at_raw = params.get("scheduled_at")
    if not scheduled_at_raw:
        return None

    try:
        eta = datetime.fromisoformat(scheduled_at_raw)
    except (TypeError, ValueError):
        logger.warning("task_id=%s bad scheduled_at=%r, skipping", task.id, scheduled_at_raw)
        return None

    if eta > now:
        return None  # not due yet

    body = params.get("body") or params.get("message") or ""
    if not body.strip():
        logger.warning("task_id=%s scheduled but empty body, skipping", task.id)
        return None

    channel = "call" if tool == "call_tool" else "sms"
    return body, channel


def scan_once(db: Session) -> int:
    """One sweep. Returns the number of tasks fired (for observability)."""
    now = datetime.now().astimezone()

    pending = (
        db.query(DBTask)
        .filter(DBTask.status == TaskStatus.PENDING)
        .all()
    )

    fired = 0
    for task in pending:
        ready = _due_message(task, now)
        if ready is None:
            continue
        message, channel = ready

        # Claim the task by flipping PENDING -> IN_PROGRESS before doing
        # any work. If another tick or a celery worker races us, whoever
        # wins commits first and the other will see IN_PROGRESS and skip.
        try:
            update_task_status(db, task.id, TaskStatus.IN_PROGRESS)
        except Exception as exc:
            logger.warning("task_id=%s claim failed: %s", task.id, exc)
            continue

        user = get_user_by_id(db, task.user_id)
        if user is None:
            logger.warning("task_id=%s user gone, marking failed", task.id)
            try:
                mark_task_failed(db, task.id)
            except Exception:
                pass
            continue

        logger.info(
            "task_id=%s firing scheduled %s (eta passed)", task.id, channel,
        )
        try:
            result = notify_user(
                db, user, message=message, channel=channel,
                force=True, task_id=task.id,
            )
        except Exception as exc:
            logger.error("task_id=%s notify_user raised: %s", task.id, exc)
            try:
                mark_task_failed(db, task.id)
            except Exception:
                pass
            continue

        try:
            if result.get("status") == "ok":
                mark_task_complete(db, task.id)
                fired += 1
            else:
                logger.warning("task_id=%s notify_user non-ok: %s", task.id, result)
                mark_task_failed(db, task.id)
        except Exception as exc:
            logger.error("task_id=%s status close failed: %s", task.id, exc)

    return fired


async def run_loop(interval_seconds: int = SCAN_INTERVAL_SECONDS) -> None:
    """Forever-loop, scheduled inside the FastAPI lifespan. Cancellation
    bubbles out naturally on shutdown -- asyncio.CancelledError exits the
    while loop without logging an error."""
    logger.info("scheduled_task_scanner loop starting, interval=%ds", interval_seconds)
    while True:
        try:
            with session_scope() as db:
                fired = scan_once(db)
            if fired:
                logger.info("scheduled_task_scanner fired %d task(s) this tick", fired)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Never let one bad tick kill the scanner -- log and try again
            # next interval. The DB may have been briefly unavailable, the
            # outbound SMS provider may have flapped, etc.
            logger.exception("scheduled_task_scanner tick failed: %s", exc)
        await asyncio.sleep(interval_seconds)
