#providers endpoints -- preferred service providers (dentist, pediatrician, etc.).
#
#   GET    /api/users/{user_id}/providers
#   POST   /api/users/{user_id}/providers
#   GET    /api/users/{user_id}/providers/{provider_id}
#   PATCH  /api/users/{user_id}/providers/{provider_id}
#   DELETE /api/users/{user_id}/providers/{provider_id}
#
#the list endpoint accepts ?specialty= for the orchestrator's "find the user's
#dentist" lookup.

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas.provider import ProviderCreate, ProviderResponse, ProviderUpdate
from services.provider_service import (
    create_provider,
    delete_provider,
    find_providers_by_specialty,
    get_provider,
    list_providers,
    update_provider,
)

router = APIRouter(
    prefix="/api/users/{user_id}/providers",
    tags=["providers"],
)


@router.get("", response_model=list[ProviderResponse])
def list_(
    user_id: UUID,
    specialty: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if specialty:
        return find_providers_by_specialty(db, user_id, specialty)
    return list_providers(db, user_id)


@router.post("", response_model=ProviderResponse, status_code=201)
def create(user_id: UUID, payload: ProviderCreate, db: Session = Depends(get_db)):
    try:
        return create_provider(
            db,
            user_id=user_id,
            name=payload.name,
            specialty=payload.specialty,
            practice=payload.practice,
        )
    except ValueError as exc:
        msg = str(exc)
        status = 404 if msg == "User not found" else 400
        raise HTTPException(status_code=status, detail=msg)


@router.get("/{provider_id}", response_model=ProviderResponse)
def get(user_id: UUID, provider_id: UUID, db: Session = Depends(get_db)):
    provider = get_provider(db, user_id, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.patch("/{provider_id}", response_model=ProviderResponse)
def patch(
    user_id: UUID,
    provider_id: UUID,
    payload: ProviderUpdate,
    db: Session = Depends(get_db),
):
    try:
        return update_provider(
            db,
            user_id=user_id,
            provider_id=provider_id,
            name=payload.name,
            specialty=payload.specialty,
            practice=payload.practice,
        )
    except ValueError as exc:
        msg = str(exc)
        status = 404 if msg == "Provider not found" else 400
        raise HTTPException(status_code=status, detail=msg)


@router.delete("/{provider_id}", status_code=204)
def remove(user_id: UUID, provider_id: UUID, db: Session = Depends(get_db)):
    if not delete_provider(db, user_id, provider_id):
        raise HTTPException(status_code=404, detail="Provider not found")
    return None
