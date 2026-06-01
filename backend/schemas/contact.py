#pydantic schemas for contacts (third parties G may call/text)
#role/org/phone are optional -- only `name` is required.

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str | None = Field(default=None, max_length=120)
    org: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)


class ContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: str | None = Field(default=None, max_length=120)
    org: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)


class ContactResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    role: str | None
    org: str | None
    phone: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
