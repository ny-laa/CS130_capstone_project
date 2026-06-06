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
from services.plan_step_executor import execute_step
from services.task_service import (
    mark_task_complete,
    mark_task_failed,
    update_task_status,
)
from services.user_service import get_user_by_id

logger = logging.getLogger("backend.services.scheduled_task_scanner")

# Tools the scanner can fire as a safety-net for celery. Mirrors what
# dispatch.run_plan accepts via scheduled_at.
_SCHEDULABLE_TOOLS = ("sms_tool", "call_tool", "business_call_tool")

# Tick cadence. Scheduled reminders rarely need sub-minute precision and
# we don't want to hammer the DB. 30s is a reasonable balance.
SCAN_INTERVAL_SECONDS = 30


def _first_step(task: DBTask) -> dict[str, Any] | None:
    steps = task.plan_steps
    if not isinstance(steps, list) or not steps:
        return None
    first = steps[0]
    return first if isinstance(first, dict) else None


def _due_step(task: DBTask, now: datetime) -> dict | None:
    """If this task's first plan_step is a schedulable step whose
    scheduled_at has passed, return the step. Otherwise None (scanner
    skips it -- not due, not schedulable, or malformed).
    """
    step = _first_step(task)
    if step is None:
        return None

    tool = step.get("tool")
    if tool not in _SCHEDULABLE_TOOLS:
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

    return step


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
        step = _due_step(task, now)
        if step is None:
            continue

        # Claim the task by flipping PENDING -> IN_PROGRESS before doing
        # any work. If celery races us, whoever commits first wins; the
        # other side will see IN_PROGRESS and skip.
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

        tool = step.get("tool")
        logger.info("task_id=%s firing scheduled tool=%s (eta passed)", task.id, tool)

        # sms_tool / call_tool keep going through notify_user so outbound
        # message rows + channel routing + history work exactly the same
        # as notify_user_task does. Other tools (business_call_tool, etc.)
        # use the generic executor.
        try:
            if tool in ("sms_tool", "call_tool"):
                params = step.get("params") or {}
                body = params.get("body") or params.get("message") or ""
                if not body.strip():
                    logger.warning("task_id=%s scheduled but empty body, marking failed", task.id)
                    mark_task_failed(db, task.id)
                    continue
                channel = "call" if tool == "call_tool" else "sms"
                result = notify_user(
                    db, user, message=body, channel=channel,
                    force=True, task_id=task.id,
                )
            else:
                result = execute_step(db, user, step)
        except Exception as exc:
            logger.error("task_id=%s execute raised: %s", task.id, exc)
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
                logger.warning("task_id=%s non-ok result: %s", task.id, result)
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
