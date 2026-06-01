#family members endpoints -- nested under /api/users/{user_id} so the user
#context is always explicit. all reads/writes are scoped to that user_id at
#the service layer (see services/family_member_service.py).
#
#   GET    /api/users/{user_id}/family-members
#   POST   /api/users/{user_id}/family-members
#   GET    /api/users/{user_id}/family-members/{member_id}
#   PATCH  /api/users/{user_id}/family-members/{member_id}
#   DELETE /api/users/{user_id}/family-members/{member_id}

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas.family_member import (
    FamilyMemberCreate,
    FamilyMemberResponse,
    FamilyMemberUpdate,
)
from services.family_member_service import (
    create_family_member,
    delete_family_member,
    get_family_member,
    list_family_members,
    update_family_member,
)

router = APIRouter(
    prefix="/api/users/{user_id}/family-members",
    tags=["family-members"],
)


@router.get("", response_model=list[FamilyMemberResponse])
def list_(user_id: UUID, db: Session = Depends(get_db)):
    return list_family_members(db, user_id)


@router.post("", response_model=FamilyMemberResponse, status_code=201)
def create(
    user_id: UUID, payload: FamilyMemberCreate, db: Session = Depends(get_db)
):
    try:
        return create_family_member(
            db, user_id=user_id, name=payload.name, relation=payload.relation
        )
    except ValueError as exc:
        msg = str(exc)
        status = 404 if msg == "User not found" else 400
        raise HTTPException(status_code=status, detail=msg)


@router.get("/{member_id}", response_model=FamilyMemberResponse)
def get(user_id: UUID, member_id: UUID, db: Session = Depends(get_db)):
    member = get_family_member(db, user_id, member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Family member not found")
    return member


@router.patch("/{member_id}", response_model=FamilyMemberResponse)
def patch(
    user_id: UUID,
    member_id: UUID,
    payload: FamilyMemberUpdate,
    db: Session = Depends(get_db),
):
    try:
        return update_family_member(
            db,
            user_id=user_id,
            member_id=member_id,
            name=payload.name,
            relation=payload.relation,
        )
    except ValueError as exc:
        msg = str(exc)
        status = 404 if msg == "Family member not found" else 400
        raise HTTPException(status_code=status, detail=msg)


@router.delete("/{member_id}", status_code=204)
def remove(user_id: UUID, member_id: UUID, db: Session = Depends(get_db)):
    if not delete_family_member(db, user_id, member_id):
        raise HTTPException(status_code=404, detail="Family member not found")
    return None
