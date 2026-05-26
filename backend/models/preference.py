#preferences table - key value pairs per user
#things like digest_time, auto_confirm_categories etc

from uuid import UUID

from sqlalchemy import ForeignKey, PrimaryKeyConstraint, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Preference(Base):
    __tablename__ = "preferences"
    __table_args__ = (
        #composite pk (user_id, key) -- one row per user per key
        PrimaryKeyConstraint("user_id", "key", name="pk_preferences_user_key"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    key: Mapped[str] = mapped_column(String(100))  #e.g. 'digest_time'
    value: Mapped[str] = mapped_column(Text)  #serialized

    user = relationship("User", back_populates="preferences")

    def __repr__(self) -> str:
        return f"<Preference user_id={self.user_id} {self.key}={self.value!r}>"
