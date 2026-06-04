# basic mock tests for  morning digest flow

from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from workers.celery_app import app
from workers.tasks.morning_digest import (
    _today_time_window,
    format_morning_digest,
    send_morning_digest_for_user,
    send_morning_digests_task,
)


def _make_user(calendar_token="fake-calendar-token"):
    # simple fake user obj for digest tests
    user = MagicMock()
    user.id = uuid4()
    user.phone_number = "+14106522198"
    user.calendar_token = calendar_token
    return user


def test_empty_calendar_returns_friendly_message():
    result = format_morning_digest([])

    assert "Good morning!" in result
    assert "do not have any calendar events today" in result # a bit hard coded test, but good for now 


def test_format_morning_digest_with_events(): #tests BOTH all day event + regular timedd event 
    events = [
        {
            "summary": "Dentist appointment",
            "start": {"dateTime": "2026-06-03T17:00:00Z"},
            "location": "Westwood",
        },
        {
            "summary": "Memorial Day holiday",
            "start": {"date": "2026-06-03"},
        },
    ]

    result = format_morning_digest(events)

    assert "Here is your schedule for today" in result
    assert "10:00 AM: Dentist appointment at Westwood" in result
    assert "All day: Memorial Day holiday" in result


def test_today_time_window_uses_full_local_day():
    # June uses daylight saving time in LA so midnight LA = 07:00 UTC
    fake_now = datetime(2026, 6, 3, 9, 30)

    time_min, time_max = _today_time_window(now=fake_now)

    assert time_min == "2026-06-03T07:00:00Z"
    assert time_max == "2026-06-04T07:00:00Z"


def test_digest_skips_user_without_calendar_token(): #should not crash, just skip! 
    db = MagicMock()
    user = _make_user(calendar_token=None)

    result = send_morning_digest_for_user(
        db=db,
        user=user,
    )

    assert result == {
        "status": "skipped_missing_calendar_token",
        "event_count": 0,
    }


@patch("workers.tasks.morning_digest.notify_user")
def test_digest_reads_calendar_and_notifies_user(mock_notify_user):
    db = MagicMock()
    user = _make_user()
    calendar_tool = MagicMock()

    calendar_tool.read.return_value = [
        {
            "summary": "Pick up kids",
            "start": {"dateTime": "2026-06-03T22:00:00Z"},
        }
    ]

    mock_notify_user.return_value = {
        "status": "ok",
        "channel": "sms",
        "sid": "SM123",
        "error": None,
    }

    result = send_morning_digest_for_user(
        db=db,
        user=user,
        calendar_tool=calendar_tool,
        now=datetime(2026, 6, 3, 8, 0),
    )

    calendar_tool.read.assert_called_once_with(
        access_token="fake-calendar-token",
        time_min="2026-06-03T07:00:00Z",
        time_max="2026-06-04T07:00:00Z",
        max_results=50,
    )

    mock_notify_user.assert_called_once()
    assert "Pick up kids" in mock_notify_user.call_args.kwargs["message"]
    assert mock_notify_user.call_args.kwargs["force"] is True
    assert result["status"] == "ok"
    assert result["event_count"] == 1


@patch("workers.tasks.morning_digest.send_morning_digest_for_user")
@patch("workers.tasks.morning_digest.session_scope")
def test_batch_task_processes_eligible_users(
    mock_session_scope,
    mock_send_digest,
):
    db = MagicMock()
    user_one = _make_user()
    user_two = _make_user()

    # session_scope() is a context manager so __enter__ returns our fake db
    mock_session_scope.return_value.__enter__.return_value = db

    db.query.return_value.filter.return_value.all.return_value = [
        user_one,
        user_two,
    ]

    mock_send_digest.return_value = {
        "status": "ok",
        "event_count": 1,
    }

    result = send_morning_digests_task.run()

    assert mock_send_digest.call_count == 2
    assert result["status"] == "completed"
    assert result["processed_users"] == 2
    assert len(result["results"]) == 2


def test_celery_beat_schedule_exists():
    schedule = app.conf.beat_schedule["send-morning-digests-every-day"]

    assert schedule["task"] == "send_morning_digests"
    assert str(schedule["schedule"]) == "<crontab: 0 8 * * * (m/h/dM/MY/d)>"