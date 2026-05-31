# basic mock tests for task service db helpers

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest

from models.datatypes import TaskStatus, TaskType, Tools
from models.task import Task as DBTask
from services.task_service import (
    _serialize_plan_steps,
    create_task,
    get_task_by_id,
    get_tasks_by_status,
    get_tasks_for_user,
    mark_task_complete,
    set_escalation_pending,
    update_task_status,
)


def test_create_task():
    db = MagicMock()
    user_id = uuid4()

    result = create_task(
        db=db,
        user_id=user_id,
        task_type="reminder",
        description="Remind parent to pick up Radhika at 3pm",
        plan_steps=[
            {
                "tool": "sms_tool",
                "params": {"message": "Pick up Radhika"},
                "status": "PENDING",
            }
        ],
    )

    assert isinstance(result, DBTask)
    assert result.user_id == user_id
    assert result.type == "reminder"
    assert result.description == "Remind parent to pick up Radhika at 3pm"
    assert result.status == TaskStatus.PENDING

    assert result.plan_steps == [
        {
            "tool": "sms_tool",
            "params": {"message": "Pick up Radhika"},
            "status": "PENDING",
        }
    ]

    db.add.assert_called_once_with(result)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(result)


def test_create_task_rejects_empty_description():
    db = MagicMock()

    with pytest.raises(ValueError, match="Task description cannot be empty"):
        create_task(
            db=db,
            user_id=uuid4(),
            task_type="reminder",
            description="   ",
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_serialize_plan_steps_handles_enum_values():
    result = _serialize_plan_steps(
        [
            {
                "tool": Tools.SMS_TOOL,
                "params": {"message": "Hello"},
                "status": TaskStatus.PENDING,
            }
        ]
    )

    assert result == [
        {
            "tool": "sms_tool",
            "params": {"message": "Hello"},
            "status": "PENDING",
        }
    ]


def test_get_task_by_id():
    db = MagicMock()
    task_id = uuid4()
    fake_task = MagicMock()

    db.get.return_value = fake_task

    result = get_task_by_id(db, task_id)

    assert result == fake_task
    db.get.assert_called_once_with(DBTask, task_id)


def test_get_tasks_for_user():
    db = MagicMock()
    user_id = uuid4()
    fake_tasks = [MagicMock(), MagicMock()]

    query = db.query.return_value
    filtered = query.filter.return_value
    ordered = filtered.order_by.return_value
    limited = ordered.limit.return_value
    limited.all.return_value = fake_tasks

    result = get_tasks_for_user(
        db=db,
        user_id=user_id,
        limit=10,
    )

    assert result == fake_tasks
    db.query.assert_called_once_with(DBTask)
    ordered.limit.assert_called_once_with(10)
    limited.all.assert_called_once()


def test_get_tasks_by_status():
    db = MagicMock()
    fake_tasks = [MagicMock()]

    query = db.query.return_value
    filtered = query.filter.return_value
    ordered = filtered.order_by.return_value
    ordered.all.return_value = fake_tasks

    result = get_tasks_by_status(
        db=db,
        status="PENDING",
    )

    assert result == fake_tasks
    db.query.assert_called_once_with(DBTask)
    ordered.all.assert_called_once()


@patch("services.task_service.get_task_by_id")
def test_update_task_status(mock_get_task_by_id):
    db = MagicMock()
    task_id = uuid4()
    fake_task = MagicMock()

    mock_get_task_by_id.return_value = fake_task

    result = update_task_status(
        db=db,
        task_id=task_id,
        status="IN_PROGRESS",
    )

    assert result == fake_task
    assert fake_task.status == TaskStatus.IN_PROGRESS
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(fake_task)


@patch("services.task_service.get_task_by_id")
def test_set_escalation_pending(mock_get_task_by_id):
    db = MagicMock()
    task_id = uuid4()
    fake_task = MagicMock()

    mock_get_task_by_id.return_value = fake_task

    before_call = datetime.now(timezone.utc)

    result = set_escalation_pending(
        db=db,
        task_id=task_id,
        timeout_minutes=30,
    )

    after_call = datetime.now(timezone.utc)

    assert result == fake_task
    assert fake_task.status == TaskStatus.ESCALATION_PENDING
    assert fake_task.escalation_deadline is not None
    assert before_call < fake_task.escalation_deadline
    assert fake_task.escalation_deadline > after_call

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(fake_task)


@patch("services.task_service.get_task_by_id")
def test_mark_task_complete(mock_get_task_by_id):
    db = MagicMock()
    task_id = uuid4()
    fake_task = MagicMock()
    fake_task.escalation_deadline = datetime.now(timezone.utc)

    mock_get_task_by_id.return_value = fake_task

    result = mark_task_complete(
        db=db,
        task_id=task_id,
    )

    assert result == fake_task
    assert fake_task.status == TaskStatus.COMPLETED
    assert fake_task.escalation_deadline is None

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(fake_task)

