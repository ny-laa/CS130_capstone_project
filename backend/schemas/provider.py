#pydantic schemas for providers (preferred service providers)
#distinct from contacts: providers are "who to pick" rather than "who to call".

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    specialty: str | None = Field(default=None, max_length=120)
    practice: str | None = Field(default=None, max_length=160)


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    specialty: str | None = Field(default=None, max_length=120)
    practice: str | None = Field(default=None, max_length=160)


class ProviderResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    specialty: str | None
    practice: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
