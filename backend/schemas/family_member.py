#pydantic schemas for family_members (dependents shown in profile page)
#separate from the ORM model so we control what the api accepts and emits.

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FamilyMemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    relation: str | None = Field(default=None, max_length=60)
    #optional contact number so G can text/call this family member directly.
    phone_number: str | None = Field(default=None, max_length=20)


class FamilyMemberUpdate(BaseModel):
    #partial update; all fields optional. unset fields are left alone.
    name: str | None = Field(default=None, min_length=1, max_length=120)
    relation: str | None = Field(default=None, max_length=60)
    phone_number: str | None = Field(default=None, max_length=20)


class FamilyMemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    relation: str | None
    phone_number: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
