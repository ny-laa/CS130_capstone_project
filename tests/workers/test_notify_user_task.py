# unit test for the celery task body. invokes the task function directly
# (not via .delay()) so we don't need a real broker. session_scope,
# get_user_by_id, and notify_user are all mocked inline.

from unittest.mock import MagicMock, patch
from uuid import uuid4

from workers.tasks.notifications import notify_user_task


def test_task_resolves_user_and_calls_notify_user():
    user_id = uuid4()
    fake_user = MagicMock(id=user_id)

    with patch("workers.tasks.notifications.session_scope") as scope_mock, \
         patch("workers.tasks.notifications.get_user_by_id", return_value=fake_user) as get_mock, \
         patch("workers.tasks.notifications.notify_user") as notify_mock:
        scope_mock.return_value.__enter__.return_value = MagicMock()
        notify_mock.return_value = {"status": "ok", "sid": "CA1"}

        result = notify_user_task(str(user_id), "ring ring", "call")

    get_mock.assert_called_once()
    assert notify_mock.call_args.kwargs["message"] == "ring ring"
    assert notify_mock.call_args.kwargs["channel"] == "call"
    assert notify_mock.call_args.kwargs["force"] is True
    assert result["status"] == "ok"


def test_task_drops_when_user_gone():
    # user deleted between scheduling and firing -- don't crash
    with patch("workers.tasks.notifications.session_scope") as scope_mock, \
         patch("workers.tasks.notifications.get_user_by_id", return_value=None), \
         patch("workers.tasks.notifications.notify_user") as notify_mock:
        scope_mock.return_value.__enter__.return_value = MagicMock()

        result = notify_user_task(str(uuid4()), "x", "sms")

    notify_mock.assert_not_called()
    assert result["status"] == "error"
