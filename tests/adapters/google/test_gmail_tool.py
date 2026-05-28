# super basic tests for GmailTool

from unittest.mock import MagicMock, patch
import base64
import pytest
from backend.adapters.google.gmail_tool import GmailTool


def test_execute_requires_access_token():
    tool = GmailTool()

    with pytest.raises(ValueError, match="access_token is required"):
        tool.execute({
            "operation": "read",
            "query": "school newer_than:1d",
        })


def test_execute_routes_read_op(): #just testing basic flow, only read op supported for now 
    tool = GmailTool()
    tool.read = MagicMock(return_value=[])

    result = tool.execute({
        "operation": "read",
        "access_token": "fake-token",
        "query": "school newer_than:1d",
        "max_results": 5,
        "include_body": False,
    })

    assert result == []
    tool.read.assert_called_once_with(
        access_token="fake-token",
        query="school newer_than:1d",
        max_results=5,
        include_body=False,
    )


def test_get_header_finds_correct_header():
    tool = GmailTool()

    headers = [
        {"name": "From", "value": "teacher@example.com"},
        {"name": "Subject", "value": "School reminder"},
        {"name": "Date", "value": "Mon, 25 May 2026 10:00:00 -0700"},
    ]

    assert tool._get_header(headers, "Subject") == "School reminder"
    assert tool._get_header(headers, "From") == "teacher@example.com"


def test_decode_body_data():
    tool = GmailTool()

    original_text = "Testing, testing, testing!!!!!"
    encoded_text = base64.urlsafe_b64encode(original_text.encode("utf-8")).decode("utf-8")
    result = tool._decode_body_data(encoded_text)
    assert result == original_text


@patch("backend.adapters.google.gmail_tool.build")
def test_read_simplifies_emails(mock_build):
    # mock Gmail service chain:
    fake_service = MagicMock()
    mock_build.return_value = fake_service

    fake_messages_api = fake_service.users.return_value.messages.return_value
    fake_messages_api.list.return_value.execute.return_value = {
        "messages": [
            {"id": "email-123"}
        ]
    }

    fake_messages_api.get.return_value.execute.return_value = {
        "id": "email-123",
        "threadId": "thread-456",
        "snippet": "Reminder about school pickup",
        "payload": {
            "headers": [
                {"name": "From", "value": "school@example.com"},
                {"name": "To", "value": "parent@example.com"},
                {"name": "Subject", "value": "School pickup reminder"},
                {"name": "Date", "value": "Mon, 25 May 2026 10:00:00 -0700"},
            ]
        },
    }

    tool = GmailTool()

    result = tool.read(
        access_token="fake-token",
        query="school newer_than:1d",
        max_results=5,
    )

    assert result == [
        {
            "id": "email-123",
            "thread_id": "thread-456",
            "from": "school@example.com",
            "to": "parent@example.com",
            "subject": "School pickup reminder",
            "date": "Mon, 25 May 2026 10:00:00 -0700",
            "snippet": "Reminder about school pickup",
        }
    ]

    fake_messages_api.list.assert_called_once_with(
        userId="me",
        q="school newer_than:1d",
        maxResults=5,
    )