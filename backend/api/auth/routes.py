from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas.user import AuthResponse, UserLogin, UserRegister, UserResponse
from services.auth_service import create_token, login_user, register_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    try:
        user = register_user(db, name=payload.name, email=payload.email, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return AuthResponse(user=UserResponse.model_validate(user), token=create_token(user.id))


@router.post("/login", response_model=AuthResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    try:
        user = login_user(db, email=payload.email, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return AuthResponse(user=UserResponse.model_validate(user), token=create_token(user.id))
