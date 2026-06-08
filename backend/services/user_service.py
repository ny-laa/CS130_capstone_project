# user crud and token management helpers
# api routes + workers should use this service instead of querying User directly
# oauth token exchange/refresh will be handled separately in the auth layer since its not fully done yet 

import re
from uuid import UUID
from sqlalchemy.orm import Session
from models.datatypes import (
    CallUrgency,
    CommStyle,
    ConflictHandling,
    DigestContent,
    PreferredChannel,
    Tone,
)
from models.user import User
from datetime import datetime, timedelta
import httpx
from config import settings
from utils.token_crypto import encrypt_token, decrypt_token


# fields update_user_preferences will overlay onto the user row. ordering
# matches the Profile page so a diff against the UI is easy to eyeball.
_PREFERENCE_FIELDS = (
    "comm_style",
    "preferred_channel",
    "call_urgency_threshold",
    "blocked_windows",
    "keep_free_windows",
    "active_days",
    "morning_digest_enabled",
    "morning_digest_time",
    "morning_digest_content",
    "morning_digest_travel_time",
    "escalation_timeout_minutes",
    "auto_approve_low_risk",
    "max_reminders",
    "tone",
    "reminder_lead_time_minutes",
    "conflict_handling",
)


def normalize_phone(phone: str | None) -> str | None:
    # canonical phone format for storage + lookup is E.164 (+15103246787).
    # signup form may submit "5103246787" or "(510) 324-6787" while twilio
    # webhooks always send E.164 -- without normalizing, a user who signs
    # up without the +1 will look "unregistered" to every inbound sms.
    # US-centric: 10-digit -> prepend +1, 11-digit starting with 1 -> prepend +.
    # already E.164 (starts with +) -> pass through. anything else, return as-is
    # so twilio surfaces a clear error instead of us silently mangling.
    if not phone:
        return phone
    if phone.startswith("+"):
        return phone
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return phone


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    # Use user UUID to find them

    return db.get(User, user_id)


def get_user_by_phone(db: Session, phone_number: str) -> User | None:
    # SMS +  voicewebhooks can use this to identify the parent.
    # normalize so "+15103246787" (twilio) and "5103246787" (signup form)
    # resolve to the same row.
    return db.query(User).filter(User.phone_number == normalize_phone(phone_number)).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    #uses user Gmail only 
    return db.query(User).filter(User.email == email).first()


def create_user(
    db: Session,
    phone_number: str,
    email: str | None = None,
    name: str | None = None,
    comm_style: CommStyle = CommStyle.BRIEF, #set to brieff for now
    preferred_channel: PreferredChannel = PreferredChannel.SMS,
    blocked_windows: dict | list | None = None,
) -> User:

    # handles creation of new parent accoun
    # phoen number is needed since Twilio uses it to match incoming SMS + calls to registered user

    phone_number = normalize_phone(phone_number)

    #checking duplicates
    if get_user_by_phone(db, phone_number):
        raise ValueError("A user with this phone number already exists!!")

    if email and get_user_by_email(db, email):
        raise ValueError("A user with this email already exists!!")

    user = User(
        phone_number=phone_number,
        email=email,
        full_name=name,
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


#[GenAI Use] Prompt: write update_user_profile(db, user_id, full_name=None, email=None) ->
#User. patch only the fields that are non-None. raise ValueError("User not found") if the
#user doesnt exist. if the email is changing, check that no OTHER user already has it and
#raise ValueError("A user with this email already exists!!") on collision. patching to your
#own current email should be a no-op (no 409). roll back on commit failure.
#[GenAI Use] LLM response:
def is_placeholder_phone(phone_number: str | None) -> bool:
    return (
        phone_number is not None and phone_number.startswith("g_")
    )

def update_user_profile(
    db: Session,
    user_id: UUID,
    name: str | None = None,
    email: str | None = None,
    phone_number: str | None = None,
) -> User:
    #patch for the "Your Info" section of the profile page + onboarding step 1.
    #phone_number is settable only when the user currently has none (first-time
    #set during onboarding). swapping an established phone goes through a
    #separate re-verification flow that doesn't exist yet -- block here instead
    #of letting someone silently re-bind their account to a different number.

    user = get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")

    if email is not None and email != user.email:
        clash = get_user_by_email(db, email)
        if clash and clash.id != user_id:
            raise ValueError("A user with this email already exists!!")
        user.email = email

    if name is not None:
        # ORM attribute is `full_name`; column is `name`. Writing to
        # `user.name` would AttributeError.
        user.full_name = name

    if phone_number is not None and phone_number != user.phone_number:
        if user.phone_number is not None and not is_placeholder_phone(user.phone_number):
            raise ValueError(
                "Phone number can't be changed once set. Contact support to re-verify."
            )
        clash = get_user_by_phone(db, phone_number)
        if clash and clash.id != user_id:
            raise ValueError("A user with this phone number already exists!!")
        user.phone_number = normalize_phone(phone_number)

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return user
#[GenAI Use] Response end
#[GenAI Use] Reflect: the `email != user.email` guard short-circuits the duplicate check
#when a user re-saves their own email -- otherwise it would false-positive 409 against
#themselves. covered by test_update_user_profile_allows_same_email_for_same_user. error
#strings are exact-matched by api/users.py to pick 404 vs 409 status codes -- if we
#rename them we have to update the router too.


def update_user_preferences(db: Session, user_id: UUID, **updates) -> User:
    """Partial PATCH for everything under the Profile page's settings.

    Accepts any subset of `_PREFERENCE_FIELDS`. Unknown keys are ignored
    silently so a newer API contract from the frontend can't 500 the
    backend mid-rollout. None values are treated as "leave this field
    alone" -- pass explicit defaults at the API boundary if you actually
    want to clear a field.
    """
    user = get_user_by_id(db, user_id)

    if user is None:
        raise ValueError("User not found")

    for field in _PREFERENCE_FIELDS:
        value = updates.get(field)
        if value is not None:
            setattr(user, field, value)

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return user

# Used Claude to connect/update the following two functions to match the oauth changes made in oauth.py
# Based on oauth.py and user_service.py, connect and update the following two functions to match the changes made
def save_google_oauth(
    db: Session,
    user_id: UUID,
    access_token: str,
    refresh_token: str | None,
    expiry: str,
) -> User:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")

    #encrypt at rest -- access_token always; refresh_token only when we
    #actually got a fresh one back. if the caller didn't supply a new
    #refresh_token we preserve the existing (already-encrypted) value
    #verbatim so we don't double-wrap on every refresh cycle.
    existing = user.google_oauth or {}
    refresh_ct = (
        encrypt_token(refresh_token)
        if refresh_token
        else existing.get("refresh_token")
    )
    user.google_oauth = {
        "access_token": encrypt_token(access_token),
        "refresh_token": refresh_ct,
        "expiry": expiry,
    }

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return user


def get_google_oauth(db: Session, user_id: UUID) -> dict | None:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")
    #decrypt on read -- callers (calendar/gmail adapters) expect plaintext.
    #expiry stays plaintext so get_access_token can compare without a
    #decrypt round-trip on every call.
    blob = user.google_oauth
    if not blob:
        return blob
    return {
        "access_token": decrypt_token(blob.get("access_token")),
        "refresh_token": decrypt_token(blob.get("refresh_token")),
        "expiry": blob.get("expiry"),
    }


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

def refresh_token(db: Session, user_id: UUID) -> str:
    user = get_user_by_id(db, user_id)
    # error handling
    if user is None:
        raise ValueError("user not found")

    oauth = user.google_oauth
    if not oauth or not oauth.get("refresh_token"):
        raise ValueError("no refresh token found")

    #decrypt before sending to google; the stored value is ciphertext.
    refresh_plain = decrypt_token(oauth["refresh_token"])

    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_plain,
            "grant_type": "refresh_token",
        },
    )

    if response.status_code != 200:
        raise ValueError("token refresh failed")

    token = response.json()
    expire = datetime.utcnow() + timedelta(seconds = token["expires_in"])
    #re-encrypt the new access_token; refresh_token is already ciphertext
    #(google's refresh response doesn't return a new one) so we keep the
    #existing blob verbatim and skip a redundant decrypt/encrypt cycle.
    user.google_oauth = {
        "access_token": encrypt_token(token["access_token"]),
        "refresh_token": oauth["refresh_token"],
        "expiry": expire.isoformat(),
    }

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        raise

    return token["access_token"]

def get_access_token(db: Session, user_id: UUID) -> str:
    user = get_user_by_id(db, user_id)
    # error handling
    if user is None:
        raise ValueError("user not found")

    oauth = user.google_oauth
    if not oauth or not oauth.get("refresh_token"):
        raise ValueError("no refresh token found")

    expire = datetime.fromisoformat(oauth["expiry"])
    # refresh 10 minutes in advance
    if datetime.utcnow() >= expire - timedelta(minutes=10):
        return refresh_token(db, user_id)

    #stored ciphertext -- decrypt to give callers plaintext, matching
    #the contract refresh_token() returns above.
    return decrypt_token(oauth["access_token"])