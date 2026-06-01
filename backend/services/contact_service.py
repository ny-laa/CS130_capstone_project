#contacts crud helpers
#same scoping convention as family_member_service: every call takes (db, user_id)
#and verifies the contact belongs to that user.

from uuid import UUID

from sqlalchemy.orm import Session

from models.contact import Contact
from models.user import User


def list_contacts(db: Session, user_id: UUID) -> list[Contact]:
    return (
        db.query(Contact)
        .filter(Contact.user_id == user_id)
        .order_by(Contact.created_at.asc())
        .all()
    )


def get_contact(db: Session, user_id: UUID, contact_id: UUID) -> Contact | None:
    return (
        db.query(Contact)
        .filter(Contact.id == contact_id, Contact.user_id == user_id)
        .first()
    )


def create_contact(
    db: Session,
    user_id: UUID,
    name: str,
    role: str | None = None,
    org: str | None = None,
    phone: str | None = None,
) -> Contact:
    if db.get(User, user_id) is None:
        raise ValueError("User not found")

    if not name.strip():
        raise ValueError("Contact name cannot be empty")

    contact = Contact(
        user_id=user_id,
        name=name.strip(),
        role=role,
        org=org,
        phone=phone,
    )
    db.add(contact)
    try:
        db.commit()
        db.refresh(contact)
    except Exception:
        db.rollback()
        raise
    return contact


def update_contact(
    db: Session,
    user_id: UUID,
    contact_id: UUID,
    name: str | None = None,
    role: str | None = None,
    org: str | None = None,
    phone: str | None = None,
) -> Contact:
    contact = get_contact(db, user_id, contact_id)
    if contact is None:
        raise ValueError("Contact not found")

    if name is not None:
        if not name.strip():
            raise ValueError("Contact name cannot be empty")
        contact.name = name.strip()

    if role is not None:
        contact.role = role
    if org is not None:
        contact.org = org
    if phone is not None:
        contact.phone = phone

    try:
        db.commit()
        db.refresh(contact)
    except Exception:
        db.rollback()
        raise
    return contact


def delete_contact(db: Session, user_id: UUID, contact_id: UUID) -> bool:
    contact = get_contact(db, user_id, contact_id)
    if contact is None:
        return False

    db.delete(contact)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


#[GenAI Use] Prompt: write a SQLAlchemy helper find_contacts_by_name(db, user_id, name_query)
#that returns Contact rows for a given user where the name partially matches name_query,
#case-insensitive. order by created_at ascending. short-circuit and return [] if name_query
#is empty or whitespace so the orchestrator doesn't accidentally pull every contact.
#[GenAI Use] LLM response:
def find_contacts_by_name(
    db: Session, user_id: UUID, name_query: str
) -> list[Contact]:
    #case-insensitive partial match -- orchestrator uses this when the user
    #says "call Mrs. Carter" and we need to resolve which Contact row to dial.
    if not name_query.strip():
        return []

    pattern = f"%{name_query.strip()}%"
    return (
        db.query(Contact)
        .filter(Contact.user_id == user_id, Contact.name.ilike(pattern))
        .order_by(Contact.created_at.asc())
        .all()
    )
#[GenAI Use] Response end
#[GenAI Use] Reflect: ilike with %query% gives the substring match we want and the empty-
#query guard is covered by test_find_contacts_by_name_empty_query_returns_empty_list. After testing
#it appears that this should work for our project. 
