# basicc tests for user service db helpers
# mock db sessions are used for rn 

from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest
from models.datatypes import CommStyle, PreferredChannel
from models.user import User
from services.user_service import (
    create_user,
    delete_user,
    get_user_by_id,
    get_user_by_phone,
    save_google_tokens,
    update_user_preferences,
    update_user_profile,
)


def test_get_user_by_id():
    db = MagicMock()
    fake_user = MagicMock()
    user_id = uuid4()

    db.get.return_value = fake_user

    result = get_user_by_id(db, user_id)

    assert result == fake_user
    db.get.assert_called_once_with(User, user_id)


def test_get_user_by_phone():
    db = MagicMock()
    fake_user = MagicMock()

    db.query.return_value.filter.return_value.first.return_value = fake_user

    result = get_user_by_phone(db, "+13105650187")

    assert result == fake_user
    db.query.assert_called_once_with(User)


@patch("services.user_service.get_user_by_email")
@patch("services.user_service.get_user_by_phone")
def test_create_user(mock_get_by_phone, mock_get_by_email):
    db = MagicMock()
    mock_get_by_phone.return_value = None
    mock_get_by_email.return_value = None

    result = create_user(
        db=db,
        phone_number="+13105650187",
        email="parent@example.com",
    )

    assert result.phone_number == "+13105650187"
    assert result.email == "parent@example.com"
    assert result.comm_style == CommStyle.BRIEF #this is the standard onee
    assert result.preferred_channel == PreferredChannel.SMS

    db.add.assert_called_once_with(result)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(result)


@patch("services.user_service.get_user_by_phone")
def test_create_user_rejects_duplicate_phone(mock_get_by_phone):
    db = MagicMock()
    mock_get_by_phone.return_value = MagicMock()

    with pytest.raises(
        ValueError,
        match="A user with this phone number already exists!",
    ):
        create_user(
            db=db,
            phone_number="+13105650187",
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


@patch("services.user_service.get_user_by_id")
def test_update_user_preferences(mock_get_by_id):
    db = MagicMock()
    fake_user = MagicMock()
    user_id = uuid4()

    mock_get_by_id.return_value = fake_user

    result = update_user_preferences(
        db=db,
        user_id=user_id,
        comm_style=CommStyle.DETAILED,
        preferred_channel=PreferredChannel.CALL,
        blocked_windows=[{"start_time": "09:00", "end_time": "11:00"}],
    )

    assert result == fake_user
    assert fake_user.comm_style == CommStyle.DETAILED
    assert fake_user.preferred_channel == PreferredChannel.CALL
    assert fake_user.blocked_windows == [
        {"start_time": "09:00", "end_time": "11:00"}
    ]

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(fake_user)


@patch("services.user_service.get_user_by_id")
def test_save_google_tokens(mock_get_by_id):
    db = MagicMock()
    fake_user = MagicMock()
    user_id = uuid4()

    mock_get_by_id.return_value = fake_user

    result = save_google_tokens(
        db=db,
        user_id=user_id,
        calendar_token="fake-calendar-token",
        gmail_token="fake-gmail-token",
    )

    assert result == fake_user
    assert fake_user.calendar_token == "fake-calendar-token"
    assert fake_user.gmail_token == "fake-gmail-token"

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(fake_user)


@patch("services.user_service.get_user_by_id")
def test_delete_user_returns_false_if_user_not_found(mock_get_by_id):
    db = MagicMock()
    user_id = uuid4()

    mock_get_by_id.return_value = None

    result = delete_user(db, user_id)

    assert result is False
    db.delete.assert_not_called()
    db.commit.assert_not_called()


#-- new: full_name on create + update_user_profile -------------------------


@patch("services.user_service.get_user_by_email")
@patch("services.user_service.get_user_by_phone")
def test_create_user_persists_full_name(mock_phone, mock_email):
    db = MagicMock()
    mock_phone.return_value = None
    mock_email.return_value = None

    result = create_user(
        db=db,
        phone_number="+13105550199",
        email="alex@example.com",
        full_name="Alex Johnson",
    )

    assert result.full_name == "Alex Johnson"


@patch("services.user_service.get_user_by_id")
def test_update_user_profile_sets_full_name_and_email(mock_get_by_id):
    db = MagicMock()
    fake_user = MagicMock()
    fake_user.email = "old@example.com"
    mock_get_by_id.return_value = fake_user

    with patch("services.user_service.get_user_by_email", return_value=None):
        result = update_user_profile(
            db=db, user_id=uuid4(), full_name="Alex P. Johnson", email="new@example.com"
        )

    assert result is fake_user
    assert fake_user.full_name == "Alex P. Johnson"
    assert fake_user.email == "new@example.com"
    db.commit.assert_called_once()


@patch("services.user_service.get_user_by_id")
def test_update_user_profile_404_when_user_missing(mock_get_by_id):
    mock_get_by_id.return_value = None

    with pytest.raises(ValueError, match="User not found"):
        update_user_profile(MagicMock(), uuid4(), full_name="x")


@patch("services.user_service.get_user_by_id")
def test_update_user_profile_rejects_email_taken_by_other_user(mock_get_by_id):
    user_id = uuid4()
    fake_user = MagicMock(id=user_id)
    fake_user.email = "me@example.com"
    mock_get_by_id.return_value = fake_user

    other = MagicMock(id=uuid4())
    with patch("services.user_service.get_user_by_email", return_value=other):
        with pytest.raises(ValueError, match="already exists"):
            update_user_profile(MagicMock(), user_id, email="taken@example.com")


@patch("services.user_service.get_user_by_id")
def test_update_user_profile_allows_same_email_for_same_user(mock_get_by_id):
    #patching to your own current email shouldnt 409
    user_id = uuid4()
    fake_user = MagicMock(id=user_id)
    fake_user.email = "me@example.com"
    mock_get_by_id.return_value = fake_user

    #since email == current, get_user_by_email shouldnt even be consulted
    with patch("services.user_service.get_user_by_email") as mock_email:
        update_user_profile(MagicMock(), user_id, email="me@example.com")
        mock_email.assert_not_called()