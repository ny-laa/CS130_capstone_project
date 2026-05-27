#note: these tests are basic for now, will better test the logic after oauth + database is sett up 
from unittest.mock import MagicMock, patch
import pytest
from backend.adapters.google.calendar_tool import CalendarTool

def test_execute_requires_access_token(): #test to make sure error happpens if access token isn't there
    tool = CalendarTool()
    with pytest.raises(ValueError, match="access_token is required"):
        tool.execute({
            "operation": "read",
            "time_min": "2026-05-24T00:00:00Z",
            "time_max": "2026-05-25T00:00:00Z",
        })


def test_execute_routes_read_operation(): #tests the flow of exeucte func w/ read op
    tool = CalendarTool()
    tool.read = MagicMock(return_value=[])

    result = tool.execute({
        "operation": "read", #later can test other ops too 
        "access_token": "fake-token",
        "time_min": "2026-05-24T00:00:00Z",
        "time_max": "2026-05-25T00:00:00Z",
    })

    assert result == []
    tool.read.assert_called_once_with(
        access_token="fake-token",
        time_min="2026-05-24T00:00:00Z",
        time_max="2026-05-25T00:00:00Z",
        calendar_id="primary",
        max_results=10,
    )


@patch("backend.adapters.google.calendar_tool.build")
def test_read_simplifies_events(mock_build):
    #mocks the gcal service chain =>  service.events().list(...).execute()
    fake_service = MagicMock()
    mock_build.return_value = fake_service

    fake_service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "event-123",
                "summary": "Dentist appointment",
                "start": {"dateTime": "2026-05-24T15:00:00Z"},
                "end": {"dateTime": "2026-05-24T16:00:00Z"},
                "location": "UCLA Hospital",
                "description": "Checkup for Mark",
            }
        ]
    }

    tool = CalendarTool()

    result = tool.read(
        access_token="fake-token",
        time_min="2026-05-24T00:00:00Z",
        time_max="2026-05-25T00:00:00Z",
    )

    assert result == [
        {
            "id": "event-123",
            "summary": "Dentist appointment",
            "start": {"dateTime": "2026-05-24T15:00:00Z"},
            "end": {"dateTime": "2026-05-24T16:00:00Z"},
            "location": "UCLA Hospital",
            "description": "Checkup for Mark",
        }
    ]

@patch("backend.adapters.google.calendar_tool.build")
def test_check_availability_returns_busy_window(mock_build):
    fake_service = MagicMock()
    mock_build.return_value = fake_service

    fake_service.freebusy.return_value.query.return_value.execute.return_value = {
        "calendars": {
            "primary": {
                "busy": [
                    {
                        "start": "2026-05-24T15:00:00Z",
                        "end": "2026-05-24T16:00:00Z",
                    }
                ]
            }
        }
    }

    tool = CalendarTool()

    result = tool.check_availability(
        access_token="fake-token",
        start_time="2026-05-24T15:00:00Z",
        end_time="2026-05-24T16:00:00Z",
    )

    assert result == {
        "available": False,
        "busy_windows": [
            {
                "start": "2026-05-24T15:00:00Z",
                "end": "2026-05-24T16:00:00Z",
            }
        ],
    }


@patch("backend.adapters.google.calendar_tool.build")
def test_write_creates_event(mock_build):
    fake_service = MagicMock()
    mock_build.return_value = fake_service

    fake_event = {
        "id": "created-event-123",
        "summary": "Dentist appointment",
    }

    fake_service.events.return_value.insert.return_value.execute.return_value = fake_event
    tool = CalendarTool()
    event_body = {
        "summary": "Dentist appointment",
        "start": {"dateTime": "2026-05-24T15:00:00Z"},
        "end": {"dateTime": "2026-05-24T16:00:00Z"},
    }

    result = tool.write(
        access_token="fake-token",
        action="create",
        event_body=event_body,
    )

    assert result == {
        "status": "created",
        "event": fake_event,
    }

    fake_service.events.return_value.insert.assert_called_once_with(
        calendarId="primary",
        body=event_body,
    )