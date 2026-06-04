# builds a more complete user context dict for  LLM
# now includes family members, contacts, providers, and prefs! 

from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session
from models.preference import Preference
from models.user import User
from services.contact_service import list_contacts
from services.family_member_service import list_family_members
from services.provider_service import list_providers
from services.user_service import get_user_by_id


def _get_enum_value(value) -> str | None:
    # this is needed cause our enum values have a .value field, but keep this helper flexible so context building still works if field is alr a plain string
    if value is None:
        return None

    if hasattr(value, "value"):
        return value.value

    return str(value)


def _format_user(user: User) -> dict[str, Any]:
    # tokens are intentionally NOT included here for obv reaosns -- the LLM
    # only needs the booleans to know which tools are wired up.
    has_google = bool(user.google_oauth and user.google_oauth.get("access_token"))
    return {
        "user_id": str(user.id),
        # ORM Python attribute is `full_name` (mapped to the `name` column).
        # `user.name` would AttributeError. Serialize as "name" for the LLM
        # prompt since that's the natural key.
        "name": user.full_name,
        "email": user.email,

        #communication
        "comm_style": _get_enum_value(user.comm_style),
        "preferred_channel": _get_enum_value(user.preferred_channel),
        "call_urgency_threshold": _get_enum_value(user.call_urgency_threshold),

        #notification timing
        "blocked_windows": user.blocked_windows,
        "keep_free_windows": user.keep_free_windows,
        "active_days": user.active_days,

        #morning digest 
        "morning_digest_enabled": user.morning_digest_enabled,
        "morning_digest_time": user.morning_digest_time,
        "morning_digest_content": _get_enum_value(user.morning_digest_content),
        "morning_digest_travel_time": user.morning_digest_travel_time,

        #escalation behavior
        "escalation_timeout_minutes": user.escalation_timeout_minutes,
        "auto_approve_low_risk": user.auto_approve_low_risk,
        "max_reminders": user.max_reminders,

        # G's behavior
        "tone": _get_enum_value(user.tone),
        "reminder_lead_time_minutes": user.reminder_lead_time_minutes,
        "conflict_handling": _get_enum_value(user.conflict_handling),

        #integration flags
        # one google_oauth bundle covers gmail + calendar scopes.
        "has_calendar_connected": has_google,
        "has_gmail_connected": has_google,
    }


def _format_family_member(member) -> dict[str, Any]:
    return {
        "id": str(member.id),
        "name": member.name,
        "relation": member.relation,
        "phone_number": member.phone_number,
    }


def _format_contact(contact) -> dict[str, Any]:
    return {
        "id": str(contact.id),
        "name": contact.name,
        "role": contact.role,
        "org": contact.org,
        "phone": contact.phone,
    }


def _format_provider(provider) -> dict[str, Any]:
    return {
        "id": str(provider.id),
        "name": provider.name,
        "specialty": provider.specialty,
        "practice": provider.practice,
    }


def _get_preferences(db: Session, user_id: UUID) -> dict[str, str]:
    # prefss table stores key/val rows => convert to a simple dict for easier LLM context
    rows = (
        db.query(Preference)
        .filter(Preference.user_id == user_id)
        .all()
    )

    return {
        preference.key: preference.value
        for preference in rows
    }


def build_user_context(db: Session, user_id: UUID) -> dict[str, Any]:
    
    user = get_user_by_id(db, user_id)

    if user is None:
        raise ValueError("User not found")

    family_members = list_family_members(db, user_id)
    contacts = list_contacts(db, user_id)
    providers = list_providers(db, user_id)
    preferences = _get_preferences(db, user_id)

    return {
        "user": _format_user(user),
        "family_members": [
            _format_family_member(member)
            for member in family_members
        ],
        "contacts": [
            _format_contact(contact)
            for contact in contacts
        ],
        "providers": [
            _format_provider(provider)
            for provider in providers
        ],
        "preferences": preferences,
    }