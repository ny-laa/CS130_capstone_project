# approve / deny escalation endpoints (called by the frontend TaskCard buttons
# POST /api/tasks/{id}/approve will resume task, parent said go ahead
# POST /api/tasks/{id}/deny will abort task, parent said no

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from adapters.communication.sms_tool import SMSTool
from adapters.google.user_calendar_adapter import UserCalendarAdapter
from database import get_db
from models.datatypes import TaskStatus, Tools
from orchestrator.orchestrator import GOrchestrator
from orchestrator.task_planner import PlanStep, StructuredTaskPlan
from orchestrator.task_planner import Task as InMemoryTask
from services.task_service import get_task_by_id, update_task_status
from services.user_service import get_user_by_id

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

_sms = SMSTool()
_orch = GOrchestrator()


def _rebuild_in_memory_task(db_task) -> InMemoryTask:
    # reconstruct the in-memory Task from the DB row so the orchestrator can resume it
    steps = [
        PlanStep(
            tool=s.get("tool"),
            params=s.get("params", {}),
            status=TaskStatus(s.get("status", "PENDING")),
        )
        for s in (db_task.plan_steps or [])
    ]
    plan = StructuredTaskPlan(
        task_type=db_task.type,
        description=db_task.description,
        plan_steps=steps,
        response_message="",
    )
    task = InMemoryTask(
        id=db_task.id,
        user_id=db_task.user_id,
        status=db_task.status,
        task_plan=plan,
        escalation_deadline=db_task.escalation_deadline,
        created_at=db_task.created_at,
        updated_at=db_task.updated_at,
    )
    task.force_overlap = getattr(db_task, "force_overlap", False)
    return task


@router.post("/{task_id}/approve")
def approve_task(task_id: UUID, db: Session = Depends(get_db)):
    db_task = get_task_by_id(db, task_id)
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if db_task.status != TaskStatus.ESCALATION_PENDING:
        raise HTTPException(status_code=409, detail=f"Task is not pending escalation (status={db_task.status})")

    user = get_user_by_id(db, db_task.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    in_memory = _rebuild_in_memory_task(db_task)

    # UserCalendarAdapter injects calendar_token transparently; force_overlap skips the availability check
    cal_adapter = UserCalendarAdapter(user, force_overlap=in_memory.force_overlap)
    tool_registry = {
        Tools.CALENDAR_TOOL: cal_adapter,
        Tools.SMS_TOOL: _sms,
    }

    _orch.resume_task_from_reply(task=in_memory, approved=True, tool_registry=tool_registry)

    # persist the decision back to DB; inline force_overlap since task_service doesn't have it yet
    if in_memory.force_overlap:
        db_task.force_overlap = True
        db.commit()
    update_task_status(db, db_task, in_memory.status)

    return {"task_id": str(task_id), "status": in_memory.status}


@router.post("/{task_id}/deny")
def deny_task(task_id: UUID, db: Session = Depends(get_db)):
    db_task = get_task_by_id(db, task_id)
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if db_task.status != TaskStatus.ESCALATION_PENDING:
        raise HTTPException(status_code=409, detail=f"Task is not pending escalation (status={db_task.status})")

    update_task_status(db, db_task, TaskStatus.FAILED)
    return {"task_id": str(task_id), "status": TaskStatus.FAILED}
