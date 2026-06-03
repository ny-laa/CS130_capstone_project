# pydantic schemas for user related requests and responses
# separate from the ORM model so we dont expose stuff like raw tokens
#
# the column-of-truth in the User model is `name` (see models/user.py); this
# module mirrors that exactly -- no leftover `full_name` aliases.

from uuid import UUID

from pydantic import BaseModel, Field

from models.datatypes import (
    CallUrgency,
    CommStyle,
    ConflictHandling,
    DigestContent,
    PreferredChannel,
    Tone,
)


class UserCreate(BaseModel):
    phone_number: str
    email: str | None = None
    #optional at signup -- frontend collects it on the profile page later.
    name: str | None = Field(default=None, max_length=120)


class UserRegister(BaseModel):
    name: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    user: "UserResponse"
    token: str


class UserPreferencesUpdate(BaseModel):
    """Partial PATCH payload. Every field is optional; only what's sent gets
    written, leaving everything else untouched. Mirrors how the Profile page
    saves: hit Save once, ship the whole settings dict, server overlays.
    """

    # ── communication ──────────────────────────────────────────
    comm_style: CommStyle | None = None
    preferred_channel: PreferredChannel | None = None
    call_urgency_threshold: CallUrgency | None = None

    # ── notification timing ────────────────────────────────────
    blocked_windows: list | dict | None = None
    keep_free_windows: list | dict | None = None
    active_days: list[str] | None = None

    # ── morning digest ─────────────────────────────────────────
    morning_digest_enabled: bool | None = None
    morning_digest_time: str | None = Field(default=None, max_length=5)
    morning_digest_content: DigestContent | None = None
    morning_digest_travel_time: bool | None = None

    # ── escalation behavior ────────────────────────────────────
    escalation_timeout_minutes: int | None = Field(default=None, ge=5, le=120)
    auto_approve_low_risk: bool | None = None
    max_reminders: int | None = Field(default=None, ge=1, le=10)

    # ── G's behavior ───────────────────────────────────────────
    tone: Tone | None = None
    reminder_lead_time_minutes: int | None = Field(default=None, ge=1)
    conflict_handling: ConflictHandling | None = None


class UserProfileUpdate(BaseModel):
    #patch for the "Your Info" section of the profile page.
    #phone_number intentionally excluded -- changing it requires re-verification.
    name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=255)


class UserResponse(BaseModel):
    id: UUID
    name: str | None
    phone_number: str | None
    email: str | None

    # ── communication ──────────────────────────────────────────
    comm_style: CommStyle
    preferred_channel: PreferredChannel
    call_urgency_threshold: CallUrgency

    # ── notification timing ────────────────────────────────────
    blocked_windows: list | dict | None
    keep_free_windows: list | dict | None
    active_days: list | None

    # ── morning digest ─────────────────────────────────────────
    morning_digest_enabled: bool
    morning_digest_time: str | None
    morning_digest_content: DigestContent
    morning_digest_travel_time: bool

    # ── escalation behavior ────────────────────────────────────
    escalation_timeout_minutes: int
    auto_approve_low_risk: bool
    max_reminders: int

    # ── G's behavior ───────────────────────────────────────────
    tone: Tone
    reminder_lead_time_minutes: int
    conflict_handling: ConflictHandling

    model_config = {"from_attributes": True}
