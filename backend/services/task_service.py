# handles the full task lifecycle: create, update status, mark complete or failed
# this is called by both the webhook handlers and the celery workers

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from models.datatypes import TaskStatus
from models.task import Task


def get_task(db: Session, task_id: UUID) -> Task | None:
    return db.query(Task).filter(Task.id == task_id).first()


def update_task_status(db: Session, task: Task, status: TaskStatus) -> Task:
    task.status = status
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task


def set_force_overlap(db: Session, task: Task) -> Task:
    # records that the parent approved adding an event despite a calendar conflict
    task.force_overlap = True
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task
