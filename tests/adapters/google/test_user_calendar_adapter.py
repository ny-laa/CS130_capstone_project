from unittest.mock import MagicMock
import pytest
from backend.adapters.google.user_calendar_adapter import UserCalendarAdapter


def make_user(calendar_token="fake-token"):
    user = MagicMock()
    user.calendar_token = calendar_token
    return user


def test_injects_token_into_calendar_tool():
    """UserCalendarAdapter passes access_token from user into CalendarTool — plan steps need no token."""
    mock_tool = MagicMock()
    mock_tool.execute.return_value = {"available": True, "busy_windows": []}

    adapter = UserCalendarAdapter(make_user("tok-123"), calendar_tool=mock_tool)
    adapter.execute({"operation": "check_availability", "start_time": "2026-06-01T16:00:00Z", "end_time": "2026-06-01T18:00:00Z"})

    called_params = mock_tool.execute.call_args[0][0]
    assert called_params["access_token"] == "tok-123"  # token injected transparently
    assert called_params["operation"] == "check_availability"  # original params preserved


def test_raises_if_no_calendar_connected():
    """Adapter raises clearly when user has no calendar_token rather than sending None to Google API."""
    adapter = UserCalendarAdapter(make_user(calendar_token=None))
    with pytest.raises(ValueError, match="no Google Calendar connected"):
        adapter.execute({"operation": "check_availability", "start_time": "2026-06-01T16:00:00Z", "end_time": "2026-06-01T18:00:00Z"})


def test_skips_availability_check_when_force_overlap():
    """When force_overlap=True the adapter short-circuits check_availability and returns available=True."""
    mock_tool = MagicMock()
    adapter = UserCalendarAdapter(make_user(), force_overlap=True, calendar_tool=mock_tool)

    result = adapter.execute({"operation": "check_availability", "start_time": "2026-06-01T16:00:00Z", "end_time": "2026-06-01T18:00:00Z"})

    assert result["available"] is True
    assert result.get("skipped") is True
    mock_tool.execute.assert_not_called()  # Google API never hit


def test_write_still_goes_through_when_force_overlap():
    """force_overlap only skips the check step — write operations still execute normally."""
    mock_tool = MagicMock()
    mock_tool.execute.return_value = {"status": "created", "event": {}}

    adapter = UserCalendarAdapter(make_user(), force_overlap=True, calendar_tool=mock_tool)
    result = adapter.execute({"operation": "write", "action": "create", "summary": "Pick up Mary"})

    mock_tool.execute.assert_called_once()
    assert result["status"] == "created"
