# pydantic schemas for task responses. shape mirrors the ORM model so the
# Tasks page can read it directly. plan_steps is JSONB on the row so we
# pass it through as-is.

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, model_validator

from models.datatypes import TaskStatus


class TaskResponse(BaseModel):
    id: UUID
    status: TaskStatus
    type: str
    description: str
    plan_steps: list | dict | None = None
    escalation_deadline: datetime | None = None
    escalation_question: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode='after')
    def _derive_escalation_question(self):
        if self.status != TaskStatus.ESCALATION_PENDING or self.escalation_question is not None:
            return self
        steps = self.plan_steps if isinstance(self.plan_steps, list) else []
        for step in steps:
            if not isinstance(step, dict):
                continue
            result = step.get('result') or {}
            if isinstance(result, dict) and result.get('available') is False and result.get('busy_windows'):
                busy = result['busy_windows']
                conflict_str = f"{busy[0]['start']} to {busy[0]['end']}" if busy else 'that time'
                self.escalation_question = (
                    f"There's a scheduling conflict: you're busy from {conflict_str}. "
                    "Approve to add anyway or Deny."
                )
                return self
            if step.get('tool') == 'calendar_delete_tool':
                self.escalation_question = "G wants to delete a calendar event. Approve or Deny."
                return self
        self.escalation_question = "G needs your approval to proceed. Approve or Deny."
        return self
