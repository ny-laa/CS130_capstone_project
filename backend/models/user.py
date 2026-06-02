#users table - one row per registered parent
#stores phone number, email, oauth tokens, comm preferences etc
#tokens are encrypted pls dont store them in plain text

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base
from models.datatypes import CommStyle, PreferredChannel


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), unique=True, index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comm_style: Mapped[CommStyle] = mapped_column(
        Enum(CommStyle, name="comm_style", values_callable=lambda e: [m.value for m in e]),
        default=CommStyle.BRIEF,
    )
    preferred_channel: Mapped[PreferredChannel] = mapped_column(
        Enum(
            PreferredChannel,
            name="preferred_channel",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=PreferredChannel.SMS,
    )
    #[{start_time, end_time}] recurring blocks
    blocked_windows: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    #TODO encrypt before storing real tokens
    calendar_token: Mapped[str | None] = mapped_column(nullable=True)
    gmail_token: Mapped[str | None] = mapped_column(nullable=True)
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
