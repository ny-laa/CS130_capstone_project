#users table - one row per registered parent
#stores phone number, email, google oauth bundle, comm preferences, plus all
#the per-user knobs the Profile page exposes (urgency threshold, quiet hours,
#keep-free hours, morning digest config, escalation behavior, tone, etc.).
#
#tokens are encrypted pls dont store them in plain text

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base
from models.datatypes import (
    CallUrgency,
    CommStyle,
    ConflictHandling,
    DigestContent,
    PreferredChannel,
    Tone,
)


# Helper so every Enum column serializes its `.value` string into postgres
# rather than the python member name. Mirrors how comm_style /
# preferred_channel were already declared.
def _enum_col(enum_cls, name: str):
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    full_name: Mapped[str | None] = mapped_column("name", String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), unique=True, index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── communication ──────────────────────────────────────────
    comm_style: Mapped[CommStyle] = mapped_column(
        _enum_col(CommStyle, "comm_style"),
        default=CommStyle.BRIEF,
    )
    preferred_channel: Mapped[PreferredChannel] = mapped_column(
        _enum_col(PreferredChannel, "preferred_channel"),
        default=PreferredChannel.SMS,
    )
    #urgency level at which G switches from text to a phone call.
    call_urgency_threshold: Mapped[CallUrgency] = mapped_column(
        _enum_col(CallUrgency, "call_urgency"),
        default=CallUrgency.HIGH,
    )

    # ── notification timing ────────────────────────────────────
    #[{start_time, end_time}] windows G will NOT contact the parent during.
    #checked by services.notifications._in_quiet_hours.
    blocked_windows: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    #[{start_time, end_time}] windows G will NOT schedule new events into.
    #semantically distinct from blocked_windows: quiet hours gates outbound
    #messages, keep-free gates calendar writes.
    keep_free_windows: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    #list of weekday codes G is active on, e.g. ["mon","tue","wed","thu","fri"].
    #null means "every day".
    active_days: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # ── morning digest ─────────────────────────────────────────
    morning_digest_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    #"HH:MM" local-time string. celery beat is global today; once we wire
    #per-user scheduling this is what it'll read.
    morning_digest_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    morning_digest_content: Mapped[DigestContent] = mapped_column(
        _enum_col(DigestContent, "digest_content"),
        default=DigestContent.CALENDAR,
    )
    morning_digest_travel_time: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── escalation behavior ────────────────────────────────────
    escalation_timeout_minutes: Mapped[int] = mapped_column(Integer, default=30)
    auto_approve_low_risk: Mapped[bool] = mapped_column(Boolean, default=True)
    max_reminders: Mapped[int] = mapped_column(Integer, default=3)

    # ── G's behavior ───────────────────────────────────────────
    tone: Mapped[Tone] = mapped_column(
        _enum_col(Tone, "tone"),
        default=Tone.CASUAL,
    )
    #minutes before an event G fires the reminder. UI exposes 15/30/60/1440,
    #but storing as int keeps it open if we add more options.
    reminder_lead_time_minutes: Mapped[int] = mapped_column(Integer, default=60)
    conflict_handling: Mapped[ConflictHandling] = mapped_column(
        _enum_col(ConflictHandling, "conflict_handling"),
        default=ConflictHandling.SUGGEST,
    )

    # ── google integration ────────────────────────────────────
    #access_token / refresh_token / expiry bundle. populated by the oauth
    #callback in api/auth/oauth.py. tokens are encrypted at rest via
    #utils.token_crypto (fernet/MultiFernet); expiry stays plaintext so
    #services.user_service.get_access_token can compare without decrypt.
    #all reads/writes go through services.user_service -- never touch
    #user.google_oauth directly or you'll bypass crypto.
    google_oauth: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship(
        "Preference", back_populates="user", cascade="all, delete-orphan"
    )
    family_members = relationship(
        "FamilyMember", back_populates="user", cascade="all, delete-orphan"
    )
    contacts = relationship(
        "Contact", back_populates="user", cascade="all, delete-orphan"
    )
    providers = relationship(
        "Provider", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} phone={self.phone_number}>"
