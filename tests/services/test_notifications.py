# tests for notify_user -- the proactive outbound primitive that the
# scheduler/digest will call. tools (sms, call) and log_message are mocked
# inline so we don't actually hit twilio or the db.

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from models.datatypes import PreferredChannel
from services import notifications
from services.notifications import _in_quiet_hours, notify_user


def _make_user(preferred_channel=PreferredChannel.SMS, blocked_windows=None):
    u = MagicMock()
    u.id = uuid4()
    u.phone_number = "+13105550199"
    u.preferred_channel = preferred_channel
    u.blocked_windows = blocked_windows
    return u


def test_sms_channel_sends_and_logs_sms():
    user = _make_user()
    db = MagicMock()

    with patch.object(notifications, "_sms") as sms_mock, \
         patch.object(notifications, "_call") as call_mock, \
         patch("services.notifications.log_message") as log_mock:
        sms_mock.send.return_value = "SM123"
        result = notify_user(db, user, "morning digest", channel="sms")

    sms_mock.send.assert_called_once_with(to="+13105550199", body="morning digest")
    call_mock.place_call.assert_not_called()
    assert log_mock.call_args.kwargs["channel"] == "sms"
    assert log_mock.call_args.kwargs["direction"] == "outbound"
    assert result["status"] == "ok"
    assert result["sid"] == "SM123"


def test_call_channel_places_call_and_logs_voice():
    user = _make_user()
    db = MagicMock()

    with patch.object(notifications, "_sms") as sms_mock, \
         patch.object(notifications, "_call") as call_mock, \
         patch("services.notifications.log_message") as log_mock:
        call_mock.place_call.return_value = "CA123"
        result = notify_user(db, user, "reminder: pick up kids", channel="call")

    # fire-and-forget -- no callback_url passed
    call_mock.place_call.assert_called_once_with(
        to="+13105550199", message="reminder: pick up kids"
    )
    sms_mock.send.assert_not_called()
    assert log_mock.call_args.kwargs["channel"] == "voice"
    assert result["sid"] == "CA123"


def test_falls_back_to_preferred_channel():
    # no explicit channel -> use user.preferred_channel
    user = _make_user(preferred_channel=PreferredChannel.CALL)
    db = MagicMock()

    with patch.object(notifications, "_sms") as sms_mock, \
         patch.object(notifications, "_call") as call_mock, \
         patch("services.notifications.log_message"):
        notify_user(db, user, "hello")

    call_mock.place_call.assert_called_once()
    sms_mock.send.assert_not_called()


def test_quiet_hours_skips_send_and_log():
    user = _make_user(blocked_windows=[{"start_time": "09:00", "end_time": "11:00"}])
    db = MagicMock()

    with patch("services.notifications._now_hhmm", return_value="10:00"), \
         patch.object(notifications, "_sms") as sms_mock, \
         patch("services.notifications.log_message") as log_mock:
        result = notify_user(db, user, "during quiet")

    assert result["status"] == "skipped_quiet_hours"
    sms_mock.send.assert_not_called()
    log_mock.assert_not_called()  # nothing logged either -- nothing happened


def test_force_overrides_quiet_hours():
    user = _make_user(blocked_windows=[{"start_time": "09:00", "end_time": "11:00"}])
    db = MagicMock()

    with patch("services.notifications._now_hhmm", return_value="10:00"), \
         patch.object(notifications, "_sms") as sms_mock, \
         patch("services.notifications.log_message"):
        sms_mock.send.return_value = "SM999"
        result = notify_user(db, user, "urgent", force=True)

    sms_mock.send.assert_called_once()
    assert result["status"] == "ok"


def test_cross_midnight_window_blocks_correctly():
    # 22:00 -> 07:00 wraps midnight. 23:30 should be inside, 12:00 outside.
    window = [{"start_time": "22:00", "end_time": "07:00"}]
    assert _in_quiet_hours(window, "23:30") is True
    assert _in_quiet_hours(window, "03:00") is True
    assert _in_quiet_hours(window, "12:00") is False
    assert _in_quiet_hours(window, "07:00") is False  # end is exclusive
    assert _in_quiet_hours(window, "22:00") is True   # start is inclusive


def test_twilio_failure_still_logs_outbound():
    # a2p-rejected sends still appear in the UI so the demo works while
    # verification is pending -- same pattern as the webhook handlers
    user = _make_user()
    db = MagicMock()

    with patch.object(notifications, "_sms") as sms_mock, \
         patch("services.notifications.log_message") as log_mock:
        sms_mock.send.side_effect = RuntimeError("a2p pending")
        result = notify_user(db, user, "hi", channel="sms")

    assert result["status"] == "error"
    assert "a2p pending" in result["error"]
    log_mock.assert_called_once()  # logged anyway


def test_empty_message_raises():
    user = _make_user()
    db = MagicMock()
    with pytest.raises(ValueError, match="empty"):
        notify_user(db, user, "   ")
