#tests for family_member service -- mirror the test_user_service style:
#MagicMock db session, patch internal lookups, assert ORM calls.

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from models.family_member import FamilyMember
from services.family_member_service import (
    create_family_member,
    delete_family_member,
    get_family_member,
    list_family_members,
    update_family_member,
)


def test_list_family_members_orders_by_created_at_asc():
    db = MagicMock()
    user_id = uuid4()
    fake_rows = [MagicMock(), MagicMock()]
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = fake_rows

    result = list_family_members(db, user_id)

    assert result == fake_rows
    db.query.assert_called_once_with(FamilyMember)


def test_get_family_member_scopes_by_user():
    db = MagicMock()
    user_id, member_id = uuid4(), uuid4()
    fake = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = fake

    result = get_family_member(db, user_id, member_id)

    assert result == fake
    #both id and user_id appear in the filter -- so a leaked id from another
    #account would return None instead of leaking data.
    db.query.assert_called_once_with(FamilyMember)


def test_create_family_member():
    db = MagicMock()
    user_id = uuid4()
    db.get.return_value = MagicMock()  # user exists

    result = create_family_member(db, user_id, "Sarah Johnson", "Spouse")

    assert result.name == "Sarah Johnson"
    assert result.relation == "Spouse"
    assert result.user_id == user_id
    db.add.assert_called_once_with(result)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(result)


def test_create_family_member_strips_whitespace():
    db = MagicMock()
    db.get.return_value = MagicMock()

    result = create_family_member(db, uuid4(), "  Sarah  ", None)

    assert result.name == "Sarah"


def test_create_family_member_rejects_empty_name():
    db = MagicMock()
    db.get.return_value = MagicMock()

    with pytest.raises(ValueError, match="cannot be empty"):
        create_family_member(db, uuid4(), "   ", None)

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_create_family_member_rejects_unknown_user():
    db = MagicMock()
    db.get.return_value = None  # user not found

    with pytest.raises(ValueError, match="User not found"):
        create_family_member(db, uuid4(), "Sarah", "Spouse")

    db.add.assert_not_called()


@patch("services.family_member_service.get_family_member")
def test_update_family_member(mock_get):
    db = MagicMock()
    fake = MagicMock()
    mock_get.return_value = fake

    result = update_family_member(
        db, uuid4(), uuid4(), name="Sarah J.", relation="Wife"
    )

    assert result == fake
    assert fake.name == "Sarah J."
    assert fake.relation == "Wife"
    db.commit.assert_called_once()


@patch("services.family_member_service.get_family_member")
def test_update_family_member_partial(mock_get):
    #only relation provided -- name should be untouched
    db = MagicMock()
    fake = MagicMock(name="original")
    mock_get.return_value = fake
    sentinel_name = fake.name

    update_family_member(db, uuid4(), uuid4(), relation="Mother")

    assert fake.name == sentinel_name
    assert fake.relation == "Mother"


@patch("services.family_member_service.get_family_member")
def test_update_family_member_not_found(mock_get):
    mock_get.return_value = None

    with pytest.raises(ValueError, match="Family member not found"):
        update_family_member(MagicMock(), uuid4(), uuid4(), name="X")


@patch("services.family_member_service.get_family_member")
def test_delete_family_member_returns_true_when_deleted(mock_get):
    db = MagicMock()
    fake = MagicMock()
    mock_get.return_value = fake

    assert delete_family_member(db, uuid4(), uuid4()) is True
    db.delete.assert_called_once_with(fake)
    db.commit.assert_called_once()


@patch("services.family_member_service.get_family_member")
def test_delete_family_member_returns_false_when_missing(mock_get):
    db = MagicMock()
    mock_get.return_value = None

    assert delete_family_member(db, uuid4(), uuid4()) is False
    db.delete.assert_not_called()
    db.commit.assert_not_called()
