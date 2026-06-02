# pydantic schemas for message responses (audit-log api)

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from models.datatypes import MessageChannel, MessageDirection


class MessageResponse(BaseModel):
    id: UUID
    content: str
    direction: MessageDirection
    channel: MessageChannel
    timestamp: datetime
    task_id: UUID | None = None

    model_config = {"from_attributes": True}
