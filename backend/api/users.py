# registration and preferences endpoints
# POST /api/users -- create account
# PATCH /api/users/{user_id}/preferences -- update prefs after onboarding step 2

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas.user import UserCreate, UserPreferencesUpdate, UserResponse
from services.user_service import create_user, update_user_preferences

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=201)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    try:
        user = create_user(db, phone_number=payload.phone_number, email=payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return user


@router.patch("/{user_id}/preferences", response_model=UserResponse)
def patch_preferences(
    user_id: UUID, payload: UserPreferencesUpdate, db: Session = Depends(get_db)
):
    try:
        user = update_user_preferences(
            db,
            user_id=user_id,
            comm_style=payload.comm_style,
            preferred_channel=payload.preferred_channel,
            blocked_windows=payload.blocked_windows,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return user
