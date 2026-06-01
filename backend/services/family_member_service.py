#family_members crud helpers
#api routes + workers should use this service instead of touching FamilyMember directly.
#scoping convention: every read/write takes (db, user_id, ...) and enforces the
#member belongs to that user. prevents cross-account leakage if a routing bug
#ever passes the wrong user_id.

from uuid import UUID

from sqlalchemy.orm import Session

from models.family_member import FamilyMember
from models.user import User


def list_family_members(db: Session, user_id: UUID) -> list[FamilyMember]:
    #all family members for a user, oldest first (matches insertion order
    #so the profile page list stays stable across reloads).
    return (
        db.query(FamilyMember)
        .filter(FamilyMember.user_id == user_id)
        .order_by(FamilyMember.created_at.asc())
        .all()
    )


def get_family_member(
    db: Session, user_id: UUID, member_id: UUID
) -> FamilyMember | None:
    #scoped lookup -- returns None if the id exists but belongs to someone else.
    return (
        db.query(FamilyMember)
        .filter(FamilyMember.id == member_id, FamilyMember.user_id == user_id)
        .first()
    )


def create_family_member(
    db: Session,
    user_id: UUID,
    name: str,
    relation: str | None = None,
) -> FamilyMember:
    #verify the user exists -- avoids fk-violation 500s from the api.
    if db.get(User, user_id) is None:
        raise ValueError("User not found")

    if not name.strip():
        raise ValueError("Family member name cannot be empty")

    member = FamilyMember(user_id=user_id, name=name.strip(), relation=relation)
    db.add(member)
    try:
        db.commit()
        db.refresh(member)
    except Exception:
        db.rollback()
        raise
    return member


def update_family_member(
    db: Session,
    user_id: UUID,
    member_id: UUID,
    name: str | None = None,
    relation: str | None = None,
) -> FamilyMember:
    #partial update -- unset args are left as-is. pass relation=None
    #via a sentinel if you ever need to clear it (not exposed today).
    member = get_family_member(db, user_id, member_id)
    if member is None:
        raise ValueError("Family member not found")

    if name is not None:
        if not name.strip():
            raise ValueError("Family member name cannot be empty")
        member.name = name.strip()

    if relation is not None:
        member.relation = relation

    try:
        db.commit()
        db.refresh(member)
    except Exception:
        db.rollback()
        raise
    return member


def delete_family_member(db: Session, user_id: UUID, member_id: UUID) -> bool:
    #returns True if deleted, False if not found / belonged to another user.
    member = get_family_member(db, user_id, member_id)
    if member is None:
        return False

    db.delete(member)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True
