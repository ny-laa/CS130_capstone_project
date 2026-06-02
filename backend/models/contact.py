#contacts table - third parties G may need to call or text on the user's behalf
#school office, pediatrician's front desk, plumber, etc. NOT the user's family.

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    #role at the org ("Office Manager", "Pediatrician"). free-text.
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #org / employer ("Mark's School", "Cedar Medical"). optional.
    org: Mapped[str | None] = mapped_column(String(160), nullable=True)
    #phone in any format -- normalized at call-time by twilio adapter
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user = relationship("User", back_populates="contacts")

    def __repr__(self) -> str:
        return f"<Contact id={self.id} name={self.name!r} org={self.org!r}>"
