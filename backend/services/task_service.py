# handles the task lifecycle in the db
# api routes, orchestrator code, celery workers can use these helpers

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session
from models.datatypes import TaskStatus, TaskType
from models.task import Task as DBTask

logger = logging.getLogger("backend.services.task_service")


def _get_status(status: TaskStatus | str) -> TaskStatus:
    # callers can pass either TaskStatus.PENDING or "PENDING"
    if isinstance(status, TaskStatus):
        return status

    try:
        return TaskStatus(status)
    except ValueError:
        raise ValueError(f"This is an unsupported task status: {status}")


def _get_task_type(task_type: TaskType | str) -> str:
    # task type is stored as string in db
    # accepting enum values helps keep task creation consistent!
    if isinstance(task_type, TaskType):
        return task_type.value

    try:
        return TaskType(task_type).value
    except ValueError:
        raise ValueError(f"This is a unsupported task type: {task_type}")


def _serialize_plan_steps(
    plan_steps: list[dict[str, Any] | Any] | None,
) -> list[dict[str, Any]] | None:
    # handles conversionn of plan steps into dictionaries that can be saved in the JSONB column

    # orch currenctly uses PlanStep objects during execution, BUT some callers may alr have dicts, so helper supports both in casee

    if plan_steps is None:
        return None

    serialized_steps = []

    for step in plan_steps:
        if isinstance(step, dict):
            tool = step.get("tool")
            params = step.get("params", {})
            status = step.get("status", TaskStatus.PENDING)
        else:
            # supports runtime PlanStep objects w/o importing orchestrator code
            tool = getattr(step, "tool", None)
            params = getattr(step, "params", {})
            status = getattr(step, "status", TaskStatus.PENDING)

        if tool is None:
            raise ValueError("Each plan step MUST include a tool")

        # Tools + TaskStatus are string enums but saving the plain string makes the JSON stored in Postgres easier to read!
        if hasattr(tool, "value"):
            tool = tool.value

        if hasattr(status, "value"):
            status = status.value

        serialized_steps.append(
            {
                "tool": tool,
                "params": params,
                "status": status,
            }
        )

    return serialized_steps


def create_task(
    db: Session,
    user_id: UUID,
    task_type: TaskType | str,
    description: str,
    plan_steps: list[dict[str, Any] | Any] | None = None,
    status: TaskStatus | str = TaskStatus.PENDING, # most tassks start w/ PENDING status
    escalation_deadline: datetime | None = None,
) -> DBTask:
    # handles saving a newly delegated task
    # plan_steps can  be added immediately after planning or updated later 

    if not description.strip():
        raise ValueError("Task description cannot be empty")

    task = DBTask(
        user_id=user_id,
        type=_get_task_type(task_type),
        description=description,
        plan_steps=_serialize_plan_steps(plan_steps),
        status=_get_status(status),
        escalation_deadline=escalation_deadline,
    )

    db.add(task)

    try:
        db.commit()
        db.refresh(task)
    except Exception:
        db.rollback()
        raise


    logger.info("task_id=%s type=%s user_id=%s created", task.id, task.type, task.user_id)

    return task


def get_task_by_id(db: Session, task_id: UUID) -> DBTask | None:
    # retrieve 1 task using its db UUID
    return db.get(DBTask, task_id)


def get_tasks_for_user(
    db: Session,
    user_id: UUID,
    limit: int = 50,
) -> list[DBTask]:
    # newest tasks first so recent activity is easiest to find
    return (
        db.query(DBTask)
        .filter(DBTask.user_id == user_id)
        .order_by(DBTask.created_at.desc())
        .limit(limit)
        .all()
    )


def find_pending_scheduled_task(
    db: Session,
    user_id: UUID,
    scheduled_at_iso: str,
    tool_name: str,
) -> DBTask | None:
    """Find a PENDING task that's scheduled to fire at exactly the same
    ISO timestamp via the same tool (sms_tool / call_tool). Used by
    dispatch to merge duplicate reminders rather than enqueueing two
    Celery jobs that both fire at the same moment.

    Filters in Python instead of with a JSONB query so the lookup stays
    portable across sqlite (used in tests) and postgres. PENDING set
    per user is small in practice (single digits), so the cost is fine.
    """
    pending = (
        db.query(DBTask)
        .filter(DBTask.user_id == user_id, DBTask.status == TaskStatus.PENDING)
        .all()
    )
    for t in pending:
        steps = t.plan_steps if isinstance(t.plan_steps, list) else None
        if not steps:
            continue
        first = steps[0]
        if not isinstance(first, dict) or first.get("tool") != tool_name:
            continue
        params = first.get("params") or {}
        if params.get("scheduled_at") == scheduled_at_iso:
            return t
    return None


def get_tasks_by_status(
    db: Session,
    status: TaskStatus | str,
) -> list[DBTask]:
    # makes it so we can find tasks w/ a specifc status
    # can be useful to celery workrs to retrive pending tasks, also time out handling can use it to find tasks waiting for approval
 
    return (
        db.query(DBTask)
        .filter(DBTask.status == _get_status(status))
        .order_by(DBTask.created_at.asc())
        .all()
    )


def update_task_status(
    db: Session,
    task_id: UUID,
    status: TaskStatus | str,
) -> DBTask:
    task = get_task_by_id(db, task_id)

    if task is None:
        raise ValueError("Task not found")

    task.status = _get_status(status)

    try:
        db.commit()
        db.refresh(task)
    except Exception:
        db.rollback()
        raise

    return task


def update_plan_steps(
    db: Session,
    task_id: UUID,
    plan_steps: list[dict[str, Any] | Any],
) -> DBTask:
    
    #Save updated step progress after worker completes/ pauses a step
 
    task = get_task_by_id(db, task_id)

    if task is None:
        raise ValueError("Task not found")

    task.plan_steps = _serialize_plan_steps(plan_steps)

    try:
        db.commit()
        db.refresh(task)
    except Exception:
        db.rollback()
        raise

    return task


def set_escalation_pending(
    db: Session,
    task_id: UUID,
    timeout_minutes: int = 30, # set as 30 min approval window for now 
) -> DBTask:
    
    # Pause a task while waiting for user to approove

    task = get_task_by_id(db, task_id)

    if task is None:
        raise ValueError("Task not found")

    task.status = TaskStatus.ESCALATION_PENDING
    task.escalation_deadline = datetime.now(timezone.utc) + timedelta(
        minutes=timeout_minutes
    )

    try:
        db.commit()
        db.refresh(task)
    except Exception:
        db.rollback()
        raise

    return task


def mark_task_complete(db: Session, task_id: UUID) -> DBTask:
    # clear escalation deadline cause completed tasks no longer need approval
    task = get_task_by_id(db, task_id)

    if task is None:
        raise ValueError("Task not found")

    task.status = TaskStatus.COMPLETED
    task.escalation_deadline = None

    try:
        db.commit()
        db.refresh(task)
    except Exception:
        db.rollback()
        raise

    return task


def mark_task_failed(db: Session, task_id: UUID) -> DBTask:
    # clear escalation deadline cause failed tasks are no longer active
    task = get_task_by_id(db, task_id)

    if task is None:
        raise ValueError("Task not found")

    task.status = TaskStatus.FAILED
    task.escalation_deadline = None

    try:
        db.commit()
        db.refresh(task)
    except Exception:
        db.rollback()
        raise

    return task