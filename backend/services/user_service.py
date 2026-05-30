# user crud and token management helpers
# api routes + workers should use this service instead of querying User directly
# oauth token exchange/refresh will be handled separately in the auth layer since its not fully done yet 

from uuid import UUID
from sqlalchemy.orm import Session
from models.datatypes import CommStyle, PreferredChannel
from models.user import User


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    # Use user UUID to find them

    return db.get(User, user_id)


def get_user_by_phone(db: Session, phone_number: str) -> User | None:
    # SMS +  voicewebhooks can use this to identify the parent

    return db.query(User).filter(User.phone_number == phone_number).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    #uses user Gmail only 
    return db.query(User).filter(User.email == email).first()


def create_user(
    db: Session,
    phone_number: str,
    email: str | None = None,
    comm_style: CommStyle = CommStyle.BRIEF, #set to brieff for now
    preferred_channel: PreferredChannel = PreferredChannel.SMS,
    blocked_windows: dict | list | None = None,
) -> User:
    
    # handles creation of new parent accoun
    # phoen number is needed since Twilio uses it to match incoming SMS + calls to registered user

    #checking duplicates
    if get_user_by_phone(db, phone_number):
        raise ValueError("A user with this phone number already exists!!")

    if email and get_user_by_email(db, email):
        raise ValueError("A user with this email already exists!!")

    user = User(
        phone_number=phone_number,
        email=email,
        comm_style=comm_style,
        preferred_channel=preferred_channel,
        blocked_windows=blocked_windows,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return user


def update_user_preferences(
    db: Session,
    user_id: UUID,
    comm_style: CommStyle | None = None,
    preferred_channel: PreferredChannel | None = None,
    blocked_windows: dict | list | None = None,
) -> User:
    #lets user update their prefs 

    user = get_user_by_id(db, user_id)

    if user is None:
        raise ValueError("User not found")

    if comm_style is not None:
        user.comm_style = comm_style

    if preferred_channel is not None:
        user.preferred_channel = preferred_channel

    if blocked_windows is not None:
        user.blocked_windows = blocked_windows

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return user


def save_google_tokens(
    db: Session,
    user_id: UUID,
    calendar_token: str | None = None,
    gmail_token: str | None = None,
) -> User:
    # Save Google access tokens after the OAuth flow finishes.

    # Note: This func only STORESS tokens, auth layer is responsible for exchanging OAuth codes, refreshing expired tokens, encrypting tokens before production use
   
    user = get_user_by_id(db, user_id)

    if user is None:
        raise ValueError("User not found")

    if calendar_token is not None:
        user.calendar_token = calendar_token

    if gmail_token is not None:
        user.gmail_token = gmail_token

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return user


def get_calendar_token(db: Session, user_id: UUID) -> str | None:

    user = get_user_by_id(db, user_id)

    if user is None:
        raise ValueError("User not found")

    return user.calendar_token


def get_gmail_token(db: Session, user_id: UUID) -> str | None:

    user = get_user_by_id(db, user_id)

    if user is None:
        raise ValueError("User not found")

    return user.gmail_token


def delete_user(db: Session, user_id: UUID) -> bool:
    # logic returns trye is acc existed + was deleted 
    # will return false is acc not there/user not found 

    user = get_user_by_id(db, user_id)

    if user is None:
        return False

    db.delete(user)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return True