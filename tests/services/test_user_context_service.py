# basic mock tests for building user context for the LLM

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest
from models.datatypes import CommStyle, PreferredChannel
from models.preference import Preference
from services.user_context_service import (
    _get_preferences,
    build_user_context,
)


def _make_user():
    # simple fake user row for tests! 
    return SimpleNamespace(
        id=uuid4(),
        full_name="Radhika Kakkar",
        email="rads@example.com",
        comm_style=CommStyle.BRIEF,
        preferred_channel=PreferredChannel.SMS,
        blocked_windows=[{"start_time": "22:00", "end_time": "07:00"}],
        calendar_token="secret-calendar-token",
        gmail_token=None,
    )


@patch("services.user_context_service._get_preferences")
@patch("services.user_context_service.list_providers")
@patch("services.user_context_service.list_contacts")
@patch("services.user_context_service.list_family_members")
@patch("services.user_context_service.get_user_by_id")
def test_build_user_context(
    mock_get_user,
    mock_list_family,
    mock_list_contacts,
    mock_list_providers,
    mock_get_preferences,
):
    db = MagicMock()
    user = _make_user()

    family_member = SimpleNamespace(
        id=uuid4(),
        name="Emma",
        relation="Daughter",
    )

    contact = SimpleNamespace(
        id=uuid4(),
        name="Mrs. Carter",
        role="Office Manager",
        org="Mark's School",
        phone="(310) 555-0201",
    )

    provider = SimpleNamespace(
        id=uuid4(),
        name="Dr. Lee",
        specialty="Dentist",
        practice="UCLA Dental",
    )

    mock_get_user.return_value = user
    mock_list_family.return_value = [family_member]
    mock_list_contacts.return_value = [contact]
    mock_list_providers.return_value = [provider]
    mock_get_preferences.return_value = {"digest_time": "08:00"}

    result = build_user_context(db, user.id)

    assert result["user"]["user_id"] == str(user.id)
    assert result["user"]["full_name"] == "Radhika Kakkar"
    assert result["user"]["comm_style"] == "brief"
    assert result["user"]["preferred_channel"] == "sms"

    assert result["user"]["has_calendar_connected"] is True
    assert result["user"]["has_gmail_connected"] is False

    assert result["family_members"][0]["name"] == "Emma"
    assert result["family_members"][0]["relation"] == "Daughter"

    assert result["contacts"][0]["name"] == "Mrs. Carter"
    assert result["contacts"][0]["org"] == "Mark's School"

    assert result["providers"][0]["name"] == "Dr. Lee"
    assert result["providers"][0]["specialty"] == "Dentist"

    assert result["preferences"] == {"digest_time": "08:00"}


@patch("services.user_context_service.get_user_by_id")
def test_build_user_context_raises_if_user_missing(mock_get_user):
    db = MagicMock()
    mock_get_user.return_value = None

    with pytest.raises(ValueError, match="User not found"):
        build_user_context(db, uuid4())


@patch("services.user_context_service._get_preferences")
@patch("services.user_context_service.list_providers")
@patch("services.user_context_service.list_contacts")
@patch("services.user_context_service.list_family_members")
@patch("services.user_context_service.get_user_by_id")
def test_build_user_context_handles_empty_lists( #should still create context with as much info as it has 
    mock_get_user,
    mock_list_family,
    mock_list_contacts,
    mock_list_providers,
    mock_get_preferences,
):
    db = MagicMock()
    user = _make_user()

    mock_get_user.return_value = user
    mock_list_family.return_value = []
    mock_list_contacts.return_value = []
    mock_list_providers.return_value = []
    mock_get_preferences.return_value = {}

    result = build_user_context(db, user.id)

    assert result["family_members"] == []
    assert result["contacts"] == []
    assert result["providers"] == []
    assert result["preferences"] == {}


def test_context_does_not_include_raw_google_tokens():
    # raw oauth tokens should never be exposed to the LLM!
    db = MagicMock()
    user = _make_user()

    with patch(
        "services.user_context_service.get_user_by_id",
        return_value=user,
    ), patch(
        "services.user_context_service.list_family_members",
        return_value=[],
    ), patch(
        "services.user_context_service.list_contacts",
        return_value=[],
    ), patch(
        "services.user_context_service.list_providers",
        return_value=[],
    ), patch(
        "services.user_context_service._get_preferences",
        return_value={},
    ):
        result = build_user_context(db, user.id)

    assert "calendar_token" not in result["user"]
    assert "gmail_token" not in result["user"]

    assert "secret-calendar-token" not in str(result)


def test_get_preferences_returns_simple_dictionary():
    db = MagicMock()
    user_id = uuid4()

    fake_rows = [
        SimpleNamespace(key="digest_time", value="08:00"),
        SimpleNamespace(key="daily_digest_enabled", value="true"),
    ]

    db.query.return_value.filter.return_value.all.return_value = fake_rows

    result = _get_preferences(db, user_id)

    assert result == {
        "digest_time": "08:00",
        "daily_digest_enabled": "true",
    }

    db.query.assert_called_once_with(Preference)