#tests for provider service -- includes find_providers_by_specialty which
#the orchestrator uses to pick a default ("book a dentist").

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from models.provider import Provider
from services.provider_service import (
    create_provider,
    delete_provider,
    find_providers_by_specialty,
    get_provider,
    list_providers,
    update_provider,
)


def test_list_providers():
    db = MagicMock()
    fake_rows = [MagicMock()]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = fake_rows

    assert list_providers(db, uuid4()) == fake_rows
    db.query.assert_called_once_with(Provider)


def test_get_provider_scoped_by_user():
    db = MagicMock()
    fake = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = fake

    assert get_provider(db, uuid4(), uuid4()) == fake


def test_create_provider():
    db = MagicMock()
    user_id = uuid4()
    db.get.return_value = MagicMock()

    result = create_provider(
        db, user_id, name="Dr. Lee", specialty="Dentist", practice="UCLA Westside Dental"
    )

    assert result.name == "Dr. Lee"
    assert result.specialty == "Dentist"
    assert result.practice == "UCLA Westside Dental"
    db.add.assert_called_once_with(result)
    db.commit.assert_called_once()


def test_create_provider_practice_optional():
    db = MagicMock()
    db.get.return_value = MagicMock()

    result = create_provider(db, uuid4(), name="Solo Practitioner", specialty="Plumber")

    assert result.practice is None


def test_create_provider_rejects_unknown_user():
    db = MagicMock()
    db.get.return_value = None

    with pytest.raises(ValueError, match="User not found"):
        create_provider(db, uuid4(), name="Dr. Lee")


def test_create_provider_rejects_empty_name():
    db = MagicMock()
    db.get.return_value = MagicMock()

    with pytest.raises(ValueError, match="cannot be empty"):
        create_provider(db, uuid4(), name="  ")


@patch("services.provider_service.get_provider")
def test_update_provider_partial(mock_get):
    db = MagicMock()
    fake = MagicMock()
    fake.name = "Dr. Lee"
    fake.practice = "Old Practice"
    mock_get.return_value = fake

    update_provider(db, uuid4(), uuid4(), specialty="Orthodontist")

    assert fake.specialty == "Orthodontist"
    assert fake.name == "Dr. Lee"          # untouched
    assert fake.practice == "Old Practice"  # untouched


@patch("services.provider_service.get_provider")
def test_update_provider_not_found(mock_get):
    mock_get.return_value = None

    with pytest.raises(ValueError, match="Provider not found"):
        update_provider(MagicMock(), uuid4(), uuid4(), name="x")


@patch("services.provider_service.get_provider")
def test_delete_provider_true_when_deleted(mock_get):
    db = MagicMock()
    mock_get.return_value = MagicMock()

    assert delete_provider(db, uuid4(), uuid4()) is True
    db.delete.assert_called_once()


@patch("services.provider_service.get_provider")
def test_delete_provider_false_when_missing(mock_get):
    db = MagicMock()
    mock_get.return_value = None

    assert delete_provider(db, uuid4(), uuid4()) is False
    db.delete.assert_not_called()


def test_find_providers_by_specialty():
    db = MagicMock()
    fake_rows = [MagicMock()]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = fake_rows

    result = find_providers_by_specialty(db, uuid4(), "Dentist")

    assert result == fake_rows


def test_find_providers_by_specialty_empty_query_short_circuits():
    db = MagicMock()

    assert find_providers_by_specialty(db, uuid4(), "") == []
    db.query.assert_not_called()
