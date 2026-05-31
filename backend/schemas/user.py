# pydantic schemas for user related requests and responses
# separate from the ORM model so we dont expose stuff like raw tokens

from uuid import UUID

from pydantic import BaseModel

from models.datatypes import CommStyle, PreferredChannel


class UserCreate(BaseModel):
    phone_number: str
    email: str | None = None


class UserPreferencesUpdate(BaseModel):
    comm_style: CommStyle | None = None
    preferred_channel: PreferredChannel | None = None
    blocked_windows: list | dict | None = None


class UserResponse(BaseModel):
    id: UUID
    phone_number: str
    email: str | None
    comm_style: CommStyle
    preferred_channel: PreferredChannel
    blocked_windows: list | dict | None

    model_config = {"from_attributes": True}
