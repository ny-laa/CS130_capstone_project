# tests the orchestrator with a simple reminder query
# just checks that we get back a resonable structured response
# doesnt need a real api key bc we mock the claude client

import pytest
from unittest.mock import MagicMock, patch

from backend.orchestrator.orchestrator import GOrchestrator


# fake response that looks like what claude would return
MOCK_CLAUDE_RESPONSE = {
    "task_type": "reminder",
    "description": "Remind parent to pick up Jake from school at 3pm",
    "plan_steps": [
        {"tool": "sms_tool", "params": {"time": "15:00", "message": "Pick up Jake from school"}, "status": "PENDING"}
    ],
    "response_message": "Got it! I'll remind you to pick up Jake at 3pm today."
}


@pytest.fixture
def mock_orchestrator():
    # patch the ClaudeAdapter so we dont make real api calls
    with patch("backend.orchestrator.orchestrator.ClaudeAdapter") as MockAdapter:
        fake_adapter = MagicMock()
        fake_adapter.handle.return_value = MOCK_CLAUDE_RESPONSE
        MockAdapter.return_value = fake_adapter
        yield GOrchestrator()


def test_orchestrator_simple_reminder(mock_orchestrator):
    # basic smoke test — send a simple reminder request and make sure
    # the response has all the fields we expect
    query = "Remind me to pick up Jake from school at 3pm today"

    result = mock_orchestrator.handle(query)

    # should come back as a dict
    assert isinstance(result, dict)

    # check all required fields are present
    assert "task_type" in result
    assert "description" in result
    assert "plan_steps" in result
    assert "response_message" in result

    # for a reminder query the task type should be reminder
    assert result["task_type"] == "reminder"

    # plan steps should be a list
    assert isinstance(result["plan_steps"], list)
    assert len(result["plan_steps"]) > 0

    # each step needs tool, params, status
    step = result["plan_steps"][0]
    assert "tool" in step
    assert "params" in step
    assert "status" in step

    # the sms tool should be in there since we're sending a reminder
    assert step["tool"] == "sms_tool"

    # response message should be a non-empty string
    assert isinstance(result["response_message"], str)
    assert len(result["response_message"]) > 0


def test_orchestrator_simple_reminder_no_context(mock_orchestrator):
    # make sure it works without any context passed in
    query = "Can you remind me to call the dentist tomorrow at 10am?"

    result = mock_orchestrator.handle(query)

    assert result is not None
    assert result["task_type"] == "reminder"
