#family_members table - dependents / household members G can act on behalf of
#e.g. spouse, child, parent. populated from the profile page family list.

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class FamilyMember(Base):
    __tablename__ = "family_members"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    #free-text relation ("Spouse", "Son", "Daughter"). kept open so users can type custom labels.
    relation: Mapped[str | None] = mapped_column(String(60), nullable=True)
    #optional contact number -- the Profile page collects this so G can
    #text/call a family member directly when a task references them
    #("text Sarah that practice is cancelled").
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user = relationship("User", back_populates="family_members")

    def __repr__(self) -> str:
        return f"<FamilyMember id={self.id} name={self.name!r} relation={self.relation!r}>"
