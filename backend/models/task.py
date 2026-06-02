#tasks table - one row per delegated action
#tracks status (PENDING, IN_PROGRESS, ESCALATION_PENDING, COMPLETED, FAILED)
#plan_steps is a JSONB col with the ordered list of tool calls

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base
from models.datatypes import TaskStatus


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", values_callable=lambda e: [m.value for m in e]),
        default=TaskStatus.PENDING,
        index=True,
    )
    #reminder | calendar_update | information_request | morning_digest.
    #varchar(50) so new types don't need a migration.
    type: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    #ordered [{tool, params, status}]
    plan_steps: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    #true when parent approved adding a calendar event despite a detected conflict
    force_overlap: Mapped[bool] = mapped_column(default=False)
    #null unless ESCALATION_PENDING. 30-min timeout per design doc.
    escalation_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="tasks")
    messages = relationship("Message", back_populates="task")

    def __repr__(self) -> str:
        return f"<Task id={self.id} status={self.status} type={self.type}>"
