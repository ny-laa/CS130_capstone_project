# super basic mock tests for message service db helpers so can test the flows 

from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest
from models.datatypes import MessageChannel, MessageDirection
from models.message import Message
from services.message_service import (
    create_message,
    get_messages_for_task,
    get_messages_for_user,
    log_message,
)


def test_create_message():
    db = MagicMock()
    user_id = uuid4()
    task_id = uuid4()

    result = create_message(
        db=db,
        content="Remind me to pick up Radhika at 3pm",
        direction="inbound",
        channel="sms",
        user_id=user_id,
        task_id=task_id,
    )

    assert isinstance(result, Message)
    assert result.content == "Remind me to pick up Radhika at 3pm"
    assert result.direction == MessageDirection.INBOUND
    assert result.channel == MessageChannel.SMS
    assert result.user_id == user_id
    assert result.task_id == task_id

    db.add.assert_called_once_with(result)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(result)


def test_create_message_rejects_empty_content():
    db = MagicMock()

    with pytest.raises(ValueError, match="Message content cannot be empty"):
        create_message(
            db=db,
            content="   ",
            direction="inbound",
            channel="sms",
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_create_message_rejects_invalid_direction():
    db = MagicMock()

    with pytest.raises(ValueError, match="unsupported message direction"):
        create_message(
            db=db,
            content="Yello",
            direction="upside downnn",
            channel="sms",
        )

    db.add.assert_not_called()


def test_create_message_rejects_invalid_channel():
    db = MagicMock()

    with pytest.raises(ValueError, match="unsupported message channel"):
        create_message(
            db=db,
            content="Hello",
            direction="inbound",
            channel="TV",
        )

    db.add.assert_not_called()


@patch("services.message_service.create_message")
def test_log_message_calls_create_message(mock_create_message):
    db = MagicMock()
    fake_message = MagicMock()
    user_id = uuid4()

    mock_create_message.return_value = fake_message

    result = log_message(
        db=db,
        content="Your reminder is set",
        direction="outbound",
        channel="sms",
        user_id=user_id,
    )

    assert result == fake_message

    mock_create_message.assert_called_once_with(
        db=db,
        content="Your reminder is set",
        direction="outbound",
        channel="sms",
        user_id=user_id,
        task_id=None,
    )


def test_get_messages_for_user():
    db = MagicMock()
    user_id = uuid4()
    fake_messages = [MagicMock(), MagicMock()]

    query = db.query.return_value
    filtered = query.filter.return_value
    ordered = filtered.order_by.return_value
    limited = ordered.limit.return_value
    limited.all.return_value = fake_messages

    result = get_messages_for_user(
        db=db,
        user_id=user_id,
        limit=10,
    )

    assert result == fake_messages
    db.query.assert_called_once_with(Message)
    ordered.limit.assert_called_once_with(10)
    limited.all.assert_called_once()


def test_get_messages_for_task():
    db = MagicMock()
    task_id = uuid4()
    fake_messages = [MagicMock(), MagicMock()]

    query = db.query.return_value
    filtered = query.filter.return_value
    ordered = filtered.order_by.return_value
    ordered.all.return_value = fake_messages

    result = get_messages_for_task(
        db=db,
        task_id=task_id,
    )

    assert result == fake_messages
    db.query.assert_called_once_with(Message)
    ordered.all.assert_called_once()


def test_create_message_rolls_back_if_commit_fails():
    db = MagicMock()
    db.commit.side_effect = Exception("database error")

    with pytest.raises(Exception, match="database error"):
        create_message(
            db=db,
            content="Hello",
            direction="inbound",
            channel="sms",
        )

    db.rollback.assert_called_once()