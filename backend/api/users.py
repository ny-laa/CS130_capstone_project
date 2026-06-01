# registration and preferences endpoints
# POST /api/users -- create account
# PATCH /api/users/{user_id}/preferences -- update prefs after onboarding step 2
# GET /api/users/{user_id}/messages -- conversation history (audit log)

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas.message import MessageResponse
from schemas.user import (
    UserCreate,
    UserPreferencesUpdate,
    UserProfileUpdate,
    UserResponse,
)
from services.message_service import get_messages_for_user
from services.user_service import (
    create_user,
    get_user_by_id,
    update_user_preferences,
    update_user_profile,
)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=201)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    try:
        user = create_user(
            db,
            phone_number=payload.phone_number,
            email=payload.email,
            full_name=payload.full_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    #used by the profile page to hydrate the "Your Info" section.
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def patch_user(
    user_id: UUID, payload: UserProfileUpdate, db: Session = Depends(get_db)
):
    #profile page "Your Info" save -- updates full_name / email.
    #phone_number is intentionally not editable here.
    try:
        return update_user_profile(
            db, user_id=user_id, full_name=payload.full_name, email=payload.email
        )
    except ValueError as exc:
        msg = str(exc)
        status = 404 if msg == "User not found" else 409
        raise HTTPException(status_code=status, detail=msg)


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


@router.get("/{user_id}/messages", response_model=list[MessageResponse])
def list_messages(
    user_id: UUID, limit: int = 50, db: Session = Depends(get_db)
):
    # return the most recent messages for this user, newest first. used by
    # the conversations page in the UI so we can replay the thread even
    # when twilio rejected the outbound send (A2P pending).
    if get_user_by_id(db, user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    return get_messages_for_user(db, user_id, limit=limit)
