#messages table - audit log of everything sent and recieved
#direction is inbound or outbound, channel is sms or voice

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base
from models.datatypes import MessageChannel, MessageDirection


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    #nullable for unsolicited msgs (per design doc)
    task_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    #denormed for "all messages for this user" queries
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(
            MessageDirection,
            name="message_direction",
            values_callable=lambda e: [m.value for m in e],
        )
    )
    channel: Mapped[MessageChannel] = mapped_column(
        Enum(
            MessageChannel,
            name="message_channel",
            values_callable=lambda e: [m.value for m in e],
        )
    )
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    task = relationship("Task", back_populates="messages")
    user = relationship("User", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message id={self.id} direction={self.direction} channel={self.channel}>"
