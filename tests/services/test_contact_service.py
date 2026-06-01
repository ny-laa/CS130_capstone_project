#tests for contact service -- includes the orchestrator-facing
#find_contacts_by_name search helper.

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from models.contact import Contact
from services.contact_service import (
    create_contact,
    delete_contact,
    find_contacts_by_name,
    get_contact,
    list_contacts,
    update_contact,
)


def test_list_contacts():
    db = MagicMock()
    fake_rows = [MagicMock()]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = fake_rows

    assert list_contacts(db, uuid4()) == fake_rows
    db.query.assert_called_once_with(Contact)


def test_get_contact_scoped_by_user():
    db = MagicMock()
    fake = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = fake

    assert get_contact(db, uuid4(), uuid4()) == fake


def test_create_contact_persists_all_fields():
    db = MagicMock()
    user_id = uuid4()
    db.get.return_value = MagicMock()

    result = create_contact(
        db,
        user_id,
        name="Mrs. Carter",
        role="Office Manager",
        org="Mark's School",
        phone="(310) 555-0201",
    )

    assert result.name == "Mrs. Carter"
    assert result.role == "Office Manager"
    assert result.org == "Mark's School"
    assert result.phone == "(310) 555-0201"
    assert result.user_id == user_id
    db.add.assert_called_once_with(result)
    db.commit.assert_called_once()


def test_create_contact_only_name_required():
    db = MagicMock()
    db.get.return_value = MagicMock()

    result = create_contact(db, uuid4(), name="Just A Name")

    assert result.name == "Just A Name"
    assert result.role is None
    assert result.org is None
    assert result.phone is None


def test_create_contact_rejects_unknown_user():
    db = MagicMock()
    db.get.return_value = None

    with pytest.raises(ValueError, match="User not found"):
        create_contact(db, uuid4(), name="Whoever")


def test_create_contact_rejects_empty_name():
    db = MagicMock()
    db.get.return_value = MagicMock()

    with pytest.raises(ValueError, match="cannot be empty"):
        create_contact(db, uuid4(), name="")


@patch("services.contact_service.get_contact")
def test_update_contact_partial(mock_get):
    db = MagicMock()
    fake = MagicMock()
    fake.role = "Old Role"
    fake.org = "Old Org"
    mock_get.return_value = fake

    update_contact(db, uuid4(), uuid4(), phone="(310) 555-0000")

    assert fake.phone == "(310) 555-0000"
    assert fake.role == "Old Role"  # untouched
    assert fake.org == "Old Org"    # untouched


@patch("services.contact_service.get_contact")
def test_update_contact_not_found(mock_get):
    mock_get.return_value = None

    with pytest.raises(ValueError, match="Contact not found"):
        update_contact(MagicMock(), uuid4(), uuid4(), name="x")


@patch("services.contact_service.get_contact")
def test_delete_contact_true_when_deleted(mock_get):
    db = MagicMock()
    mock_get.return_value = MagicMock()

    assert delete_contact(db, uuid4(), uuid4()) is True
    db.delete.assert_called_once()


@patch("services.contact_service.get_contact")
def test_delete_contact_false_when_missing(mock_get):
    db = MagicMock()
    mock_get.return_value = None

    assert delete_contact(db, uuid4(), uuid4()) is False
    db.delete.assert_not_called()


def test_find_contacts_by_name_uses_ilike_wildcards():
    db = MagicMock()
    fake_rows = [MagicMock()]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = fake_rows

    result = find_contacts_by_name(db, uuid4(), "carter")

    assert result == fake_rows


def test_find_contacts_by_name_empty_query_returns_empty_list():
    #empty / whitespace input shouldn't return everyone -- orchestrator should
    #always have an actual name to look up.
    db = MagicMock()

    assert find_contacts_by_name(db, uuid4(), "   ") == []
    db.query.assert_not_called()
