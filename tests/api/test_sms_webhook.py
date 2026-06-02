
# tests the current sms webhook implementation, which includes LLM handling and task creation. We want to make sure that when a plan is returned, the task is created with the right info, and that if the LLM throws an error, we don't create a task.

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app
from database import get_db


FAKE_PLAN = {
    "task_type": "calendar_update",
    "description": "Dentist at 3pm",
    "plan_steps": [
        {"tool": "calendar_tool", "params": {"operation": "write", "summary": "Dentist"}, "status": "PENDING"}
    ],
    "response_message": "Adding your dentist appointment.",
}

FORM = {"From": "+13105550199", "Body": "Add dentist at 3pm"}


def _client():
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app), mock_db


def _user():
    u = MagicMock()
    u.id = "user-uuid-123"
    u.calendar_token = "fake-cal-token"
    return u


@patch("api.webhooks.sms.validate_twilio_signature", return_value=True)
@patch("api.webhooks.sms.build_user_context", return_value={"name": "Alex"})
@patch("api.webhooks.sms.log_message")
@patch("api.webhooks.sms._sms")
@patch("api.webhooks.sms.dispatch")
@patch("api.webhooks.sms._llm")
@patch("api.webhooks.sms.get_user_by_phone")
@patch("services.task_service.create_task")
def test_task_persisted_when_plan_returned(
    mock_create, mock_get_user, mock_llm, mock_dispatch, mock_sms, mock_log, mock_ctx, mock_sig
):
    # if we got a plan the DB shoudl be updates with the right info 
    client, _ = _client()
    mock_get_user.return_value = _user()
    mock_llm.handle.return_value = FAKE_PLAN
    mock_create.return_value = MagicMock(id="task-uuid")

    r = client.post("/webhooks/sms", data=FORM, headers={"X-Twilio-Signature": "x"})

    assert r.status_code == 200
    mock_create.assert_called_once()
    kw = mock_create.call_args.kwargs
    assert kw["task_type"] == "calendar_update"
    assert kw["description"] == "Dentist at 3pm"
    assert len(kw["plan_steps"]) == 1


@patch("api.webhooks.sms.validate_twilio_signature", return_value=True)
@patch("api.webhooks.sms.build_user_context", return_value={})
@patch("api.webhooks.sms.log_message")
@patch("api.webhooks.sms._sms")
@patch("api.webhooks.sms._llm")
@patch("api.webhooks.sms.get_user_by_phone")
@patch("services.task_service.create_task")
def test_task_not_persisted_on_llm_error(
    mock_create, mock_get_user, mock_llm, mock_sms, mock_log, mock_ctx, mock_sig
):
    # llm error, we shoudld NOT call create task 
    client, _ = _client()
    mock_get_user.return_value = _user()
    mock_llm.handle.side_effect = Exception("LLM down")

    r = client.post("/webhooks/sms", data=FORM, headers={"X-Twilio-Signature": "x"})

    assert r.status_code == 200
    mock_create.assert_not_called()
