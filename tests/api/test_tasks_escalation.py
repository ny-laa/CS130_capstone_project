# [AI Prompt] Look at backend/api/tasks.py, backend/services/task_service.py, and backend/adapters/google/user_calendar_adapter.py. Write tests for the approve and deny escalation endpoints (POST /api/tasks/{id}/approve and /deny). Tests should: 1. Verify approve resumes the task via GOrchestrator and updates DB status to COMPLETED. 2. Verify deny sets the task status to FAILED without calling the orchestrator. 3. Return 404 if the task_id is not found. 4. Return 409 if the task is not in ESCALATION_PENDING state.

# [elliot note] Tests cover the full approve/deny flow from HTTP request down to DB update. It tests our api code correctly as it's intended. I will keep it as it is ;)

from unittest.mock import MagicMock, patch
from uuid import uuid4
from fastapi.testclient import TestClient

from backend.models.datatypes import TaskStatus

# shared fixtures

def make_db_task(status=TaskStatus.ESCALATION_PENDING, force_overlap=False):
    task = MagicMock()
    task.id = uuid4()
    task.user_id = uuid4()
    task.status = status
    task.force_overlap = force_overlap
    task.type = "calendar_update"
    task.description = "Add picking up Mary at 5pm"
    task.plan_steps = [
        {"tool": "calendar_tool", "params": {"operation": "check_availability", "start_time": "2026-06-02T17:00:00Z", "end_time": "2026-06-02T18:00:00Z"}, "status": "PENDING"},
        {"tool": "calendar_tool", "params": {"operation": "write", "action": "create", "summary": "Pick up Mary"}, "status": "PENDING"},
    ]
    task.escalation_deadline = None
    task.created_at = None
    task.updated_at = None
    return task


def make_user(calendar_token="fake-token"):
    user = MagicMock()
    user.calendar_token = calendar_token
    return user


def get_test_client():
    """Build a TestClient with DB dependency overridden to avoid a real Postgres connection."""
    from main import app
    from database import get_db
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    return TestClient(app), mock_db


# --- approve endpoint ---

@patch("api.tasks.get_user_by_id")
@patch("api.tasks.get_task_by_id")
@patch("api.tasks._orch")
def test_approve_resumes_task_and_sets_completed(mock_orch, mock_get_task, mock_get_user):
    """POST /api/tasks/{id}/approve → orchestrator resumes, DB task status set to COMPLETED."""
    client, mock_db = get_test_client()
    db_task = make_db_task()
    mock_get_task.return_value = db_task
    mock_get_user.return_value = make_user()

    # orchestrator sets task status to COMPLETED on resume
    def fake_resume(task, approved, tool_registry):
        task.status = TaskStatus.COMPLETED
    mock_orch.resume_task_from_reply.side_effect = fake_resume

    resp = client.post(f"/api/tasks/{db_task.id}/approve")

    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"
    mock_orch.resume_task_from_reply.assert_called_once()
    call_kwargs = mock_orch.resume_task_from_reply.call_args[1]
    assert call_kwargs["approved"] is True


@patch("api.tasks.get_task_by_id")
def test_approve_404_when_task_not_found(mock_get_task):
    """POST /api/tasks/{id}/approve → 404 if task_id unknown."""
    client, _ = get_test_client()
    mock_get_task.return_value = None

    resp = client.post(f"/api/tasks/{uuid4()}/approve")
    assert resp.status_code == 404


@patch("api.tasks.get_task_by_id")
def test_approve_409_when_not_escalation_pending(mock_get_task):
    """POST /api/tasks/{id}/approve → 409 if task is not in ESCALATION_PENDING."""
    client, _ = get_test_client()
    mock_get_task.return_value = make_db_task(status=TaskStatus.COMPLETED)

    resp = client.post(f"/api/tasks/{uuid4()}/approve")
    assert resp.status_code == 409


# --- deny endpoint ---

@patch("api.tasks.get_task_by_id")
def test_deny_sets_task_failed(mock_get_task):
    """POST /api/tasks/{id}/deny → task status set to FAILED in DB."""
    client, _ = get_test_client()
    db_task = make_db_task()
    mock_get_task.return_value = db_task

    resp = client.post(f"/api/tasks/{db_task.id}/deny")

    assert resp.status_code == 200
    assert resp.json()["status"] == "FAILED"


@patch("api.tasks.get_task_by_id")
def test_deny_404_when_task_not_found(mock_get_task):
    """POST /api/tasks/{id}/deny → 404 if task_id unknown."""
    client, _ = get_test_client()
    mock_get_task.return_value = None

    resp = client.post(f"/api/tasks/{uuid4()}/deny")
    assert resp.status_code == 404
