# pydantic schemas for user related requests and responses
# separate from the ORM model so we dont expose stuff like raw tokens

from uuid import UUID

from pydantic import BaseModel, Field

from models.datatypes import CommStyle, PreferredChannel


class UserCreate(BaseModel):
    phone_number: str
    email: str | None = None
    #optional at signup -- frontend collects it on the profile page later.
    full_name: str | None = Field(default=None, max_length=120)


class UserPreferencesUpdate(BaseModel):
    comm_style: CommStyle | None = None
    preferred_channel: PreferredChannel | None = None
    blocked_windows: list | dict | None = None


class UserProfileUpdate(BaseModel):
    #patch for the "Your Info" section of the profile page.
    #phone_number intentionally excluded -- changing it requires re-verification.
    full_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=255)


class UserResponse(BaseModel):
    id: UUID
    phone_number: str
    email: str | None
    full_name: str | None
    comm_style: CommStyle
    preferred_channel: PreferredChannel
    blocked_windows: list | dict | None

    model_config = {"from_attributes": True}
