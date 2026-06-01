# tests for GET /api/users/{user_id}/messages -- audit-log endpoint that
# the conversations page will fetch from. each test sets up its own mocks
# inline + uses fastapi's dependency_overrides to swap the db session.

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from database import get_db
from main import app
from models.datatypes import MessageChannel, MessageDirection


def _make_message(content, direction, channel, user_id):
    # mimics the Message ORM object that the service returns
    m = MagicMock()
    m.id = uuid4()
    m.content = content
    m.direction = MessageDirection(direction) if isinstance(direction, str) else direction
    m.channel = MessageChannel(channel) if isinstance(channel, str) else channel
    m.timestamp = datetime.now(timezone.utc)
    m.task_id = None
    m.user_id = user_id
    return m


def _override_db():
    # the route uses get_user_by_id and get_messages_for_user, both of which we do directly
    yield MagicMock()


def test_list_messages_returns_user_history():
    user_id = uuid4()
    fake_user = MagicMock(id=user_id)
    msgs = [
        _make_message("remind me to take meds", "inbound", "sms", user_id),
        _make_message("Got it, set for 3pm.", "outbound", "sms", user_id),
    ]

    app.dependency_overrides[get_db] = _override_db
    with patch("api.users.get_user_by_id", return_value=fake_user), \
         patch("api.users.get_messages_for_user", return_value=msgs):
        client = TestClient(app)
        r = client.get(f"/api/users/{user_id}/messages")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert body[0]["content"] == "remind me to take meds"
    assert body[0]["direction"] == "inbound"
    assert body[0]["channel"] == "sms"
    assert body[1]["direction"] == "outbound"


def test_list_messages_404_when_user_not_found():
    # unknown user_id -- shouldn't leak whether there are any messages
    unknown_id = uuid4()

    app.dependency_overrides[get_db] = _override_db
    with patch("api.users.get_user_by_id", return_value=None), \
         patch("api.users.get_messages_for_user") as mock_msgs:
        client = TestClient(app)
        r = client.get(f"/api/users/{unknown_id}/messages")
    app.dependency_overrides.clear()

    assert r.status_code == 404
    mock_msgs.assert_not_called()  # never queried messages for an unknown user


def test_list_messages_honors_limit_param():
    # ?limit=N forwarded to the service so the UI can paginate later
    user_id = uuid4()
    fake_user = MagicMock(id=user_id)

    app.dependency_overrides[get_db] = _override_db
    with patch("api.users.get_user_by_id", return_value=fake_user), \
         patch("api.users.get_messages_for_user", return_value=[]) as mock_msgs:
        client = TestClient(app)
        r = client.get(f"/api/users/{user_id}/messages?limit=10")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    assert mock_msgs.call_args.kwargs["limit"] == 10
