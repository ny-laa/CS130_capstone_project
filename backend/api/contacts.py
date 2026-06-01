#contacts endpoints -- third parties G may call/text on behalf of the user.
#
#   GET    /api/users/{user_id}/contacts
#   POST   /api/users/{user_id}/contacts
#   GET    /api/users/{user_id}/contacts/{contact_id}
#   PATCH  /api/users/{user_id}/contacts/{contact_id}
#   DELETE /api/users/{user_id}/contacts/{contact_id}
#
#search by name is exposed via the list endpoint's optional ?q= param
#(orchestrator uses it to resolve "call Mrs. Carter").

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas.contact import ContactCreate, ContactResponse, ContactUpdate
from services.contact_service import (
    create_contact,
    delete_contact,
    find_contacts_by_name,
    get_contact,
    list_contacts,
    update_contact,
)

router = APIRouter(
    prefix="/api/users/{user_id}/contacts",
    tags=["contacts"],
)


@router.get("", response_model=list[ContactResponse])
def list_(
    user_id: UUID,
    q: str | None = Query(default=None, description="case-insensitive name filter"),
    db: Session = Depends(get_db),
):
    if q:
        return find_contacts_by_name(db, user_id, q)
    return list_contacts(db, user_id)


@router.post("", response_model=ContactResponse, status_code=201)
def create(user_id: UUID, payload: ContactCreate, db: Session = Depends(get_db)):
    try:
        return create_contact(
            db,
            user_id=user_id,
            name=payload.name,
            role=payload.role,
            org=payload.org,
            phone=payload.phone,
        )
    except ValueError as exc:
        msg = str(exc)
        status = 404 if msg == "User not found" else 400
        raise HTTPException(status_code=status, detail=msg)


@router.get("/{contact_id}", response_model=ContactResponse)
def get(user_id: UUID, contact_id: UUID, db: Session = Depends(get_db)):
    contact = get_contact(db, user_id, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.patch("/{contact_id}", response_model=ContactResponse)
def patch(
    user_id: UUID,
    contact_id: UUID,
    payload: ContactUpdate,
    db: Session = Depends(get_db),
):
    try:
        return update_contact(
            db,
            user_id=user_id,
            contact_id=contact_id,
            name=payload.name,
            role=payload.role,
            org=payload.org,
            phone=payload.phone,
        )
    except ValueError as exc:
        msg = str(exc)
        status = 404 if msg == "Contact not found" else 400
        raise HTTPException(status_code=status, detail=msg)


@router.delete("/{contact_id}", status_code=204)
def remove(user_id: UUID, contact_id: UUID, db: Session = Depends(get_db)):
    if not delete_contact(db, user_id, contact_id):
        raise HTTPException(status_code=404, detail="Contact not found")
    return None
