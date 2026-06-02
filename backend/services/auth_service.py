from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import settings
from models.user import User

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def create_token(user_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire},
        settings.JWT_SECRET,
        algorithm="HS256",
    )


def decode_token(token: str) -> UUID | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None


def register_user(db: Session, name: str, email: str, password: str) -> User:
    from services.user_service import get_user_by_email

    if get_user_by_email(db, email):
        raise ValueError("An account with this email already exists.")

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise
    return user


def login_user(db: Session, email: str, password: str) -> User:
    from services.user_service import get_user_by_email

    user = get_user_by_email(db, email)
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise ValueError("Invalid email or password.")
    return user
