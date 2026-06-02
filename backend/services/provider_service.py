#providers crud helpers
#orchestrator will read these when picking a default ("book a dentist" ->
#find_providers_by_specialty(user_id, "dentist")). same scoping rules as
#contact_service / family_member_service.

from uuid import UUID

from sqlalchemy.orm import Session

from models.provider import Provider
from models.user import User


def list_providers(db: Session, user_id: UUID) -> list[Provider]:
    return (
        db.query(Provider)
        .filter(Provider.user_id == user_id)
        .order_by(Provider.created_at.asc())
        .all()
    )


def get_provider(db: Session, user_id: UUID, provider_id: UUID) -> Provider | None:
    return (
        db.query(Provider)
        .filter(Provider.id == provider_id, Provider.user_id == user_id)
        .first()
    )


def create_provider(
    db: Session,
    user_id: UUID,
    name: str,
    specialty: str | None = None,
    practice: str | None = None,
) -> Provider:
    if db.get(User, user_id) is None:
        raise ValueError("User not found")

    if not name.strip():
        raise ValueError("Provider name cannot be empty")

    provider = Provider(
        user_id=user_id,
        name=name.strip(),
        specialty=specialty,
        practice=practice,
    )
    db.add(provider)
    try:
        db.commit()
        db.refresh(provider)
    except Exception:
        db.rollback()
        raise
    return provider


def update_provider(
    db: Session,
    user_id: UUID,
    provider_id: UUID,
    name: str | None = None,
    specialty: str | None = None,
    practice: str | None = None,
) -> Provider:
    provider = get_provider(db, user_id, provider_id)
    if provider is None:
        raise ValueError("Provider not found")

    if name is not None:
        if not name.strip():
            raise ValueError("Provider name cannot be empty")
        provider.name = name.strip()

    if specialty is not None:
        provider.specialty = specialty
    if practice is not None:
        provider.practice = practice

    try:
        db.commit()
        db.refresh(provider)
    except Exception:
        db.rollback()
        raise
    return provider


def delete_provider(db: Session, user_id: UUID, provider_id: UUID) -> bool:
    provider = get_provider(db, user_id, provider_id)
    if provider is None:
        return False

    db.delete(provider)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


#[GenAI Use] Prompt: write find_providers_by_specialty(db, user_id, specialty) that
#returns Provider rows for the user whose specialty matches case-insensitively. unlike the
#contacts search this should be an exact match (no wildcards) so "Dentist" doesn't pull
#"Pediatric Dentist". return [] on empty input.
#[GenAI Use] LLM response:
def find_providers_by_specialty(
    db: Session, user_id: UUID, specialty: str
) -> list[Provider]:
    #case-insensitive exact match on specialty. used by the orchestrator to
    #default to the user's chosen dentist / pediatrician / plumber.
    if not specialty.strip():
        return []

    return (
        db.query(Provider)
        .filter(
            Provider.user_id == user_id,
            Provider.specialty.ilike(specialty.strip()),
        )
        .order_by(Provider.created_at.asc())
        .all()
    )
#[GenAI Use] Response end
#[GenAI Use] Reflect: ilike without %% wildcards gives exact match while still being
#case-insensitive -- that's what we want here. covered by
#test_find_providers_by_specialty + test_find_providers_by_specialty_empty_query_short_circuits.
#May need to just return multiple providers if user has more than one in the future, but for now this is fine.


