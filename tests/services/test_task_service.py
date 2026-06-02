from unittest.mock import MagicMock, patch
from uuid import uuid4
from backend.models.datatypes import TaskStatus


def make_db_task(status=TaskStatus.ESCALATION_PENDING):
    task = MagicMock()
    task.id = uuid4()
    task.user_id = uuid4()
    task.status = status
    task.force_overlap = False
    return task


def test_get_task_returns_task():
    #get_task queries by id and returns the matching row.
    from backend.services.task_service import get_task
    db = MagicMock()
    expected = make_db_task()
    db.query.return_value.filter.return_value.first.return_value = expected

    result = get_task(db, expected.id)
    assert result is expected


def test_get_task_returns_none_when_not_found():
    #get_task returns None for unknown task_id — caller handles the 404.
    from backend.services.task_service import get_task
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    # use a random UUID that's not supposed to be fournd 
    result = get_task(db, uuid4())
    assert result is None


def test_update_task_status_commits_and_refreshes():
    #update_task_status sets status, commits, and refreshes the row.
    from backend.services.task_service import update_task_status
    db = MagicMock()
    task = make_db_task(status=TaskStatus.ESCALATION_PENDING)

    update_task_status(db, task, TaskStatus.COMPLETED)
    # see if DB gest updated by us
    assert task.status == TaskStatus.COMPLETED
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(task)


def test_set_force_overlap_flags_task():
    #set_force_overlap marks the task as overlap-approved and persists
    from backend.services.task_service import set_force_overlap
    db = MagicMock()
    task = make_db_task()
    assert task.force_overlap is False

    set_force_overlap(db, task) # see it it actually works 
    assert task.force_overlap is True
    db.commit.assert_called_once()
