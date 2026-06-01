#providers table - preferred service providers G defaults to when booking/referring
#dentist, pediatrician, plumber, etc. distinct from contacts: providers are
#"who to pick" rather than "who to call".

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    #specialty / trade ("Dentist", "Pediatrician", "Plumber"). free-text.
    specialty: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #practice / business name ("UCLA Westside Dental"). optional for solo providers.
    practice: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user = relationship("User", back_populates="providers")

    def __repr__(self) -> str:
        return f"<Provider id={self.id} name={self.name!r} specialty={self.specialty!r}>"
