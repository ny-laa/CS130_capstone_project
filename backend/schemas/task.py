# pydantic schemas for task responses. shape mirrors the ORM model so the
# Tasks page can read it directly. plan_steps is JSONB on the row so we
# pass it through as-is.

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from models.datatypes import TaskStatus


class TaskResponse(BaseModel):
    id: UUID
    status: TaskStatus
    type: str
    description: str
    plan_steps: list | dict | None = None
    escalation_deadline: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
