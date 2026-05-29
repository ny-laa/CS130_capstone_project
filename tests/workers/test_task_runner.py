from unittest.mock import MagicMock, patch
from backend.orchestrator.task_planner import TaskPlanner, StructuredTaskPlan, Task, PlanStep
from backend.workers.task_runner import TaskRunner
from backend.models.datatypes import TaskType, TaskStatus, Tools
import os 
from backend.adapters.llm.claude_adapter import ClaudeAdapter
from uuid import uuid4
import pytest
from datetime import datetime, timezone

def make_task(steps):
    plan = StructuredTaskPlan(
        task_type= TaskType.REMINDER,
        description="test",
        plan_steps=steps,
        response_message="ok"
    )
    # make a dummy task 
    return Task(
        id=uuid4(),
        user_id=uuid4(),
        status=TaskStatus.PENDING,
        task_plan=plan,
        escalation_deadline=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

def test_complete_simple_task():
    mock_tool = MagicMock()
    steps=[PlanStep(tool=Tools.SMS_TOOL, params={"message": "hi"}, status=TaskStatus.PENDING)]
    task = make_task(steps)

    # simpel task to send a mesage. 
    
    runner = TaskRunner(tool_registry={Tools.SMS_TOOL:mock_tool})
    runner.run(task) # run task with given tools
    mock_tool.execute.assert_called_once_with({"message":"hi"}) # aprameter passing should work correctly!

    assert task.status == TaskStatus.COMPLETED # complete


def test_runner_pause_on_destructive_step():
    mock_tool = MagicMock()
    steps = [
        PlanStep(tool=Tools.SMS_TOOL, params={}, status=TaskStatus.PENDING),
        PlanStep(tool=Tools.CALENDAR_DELETE_TOOL, params={}, status=TaskStatus.PENDING)
    ]
    # desctructive!!! expect stop to escalation
    task = make_task(steps)
    runner = TaskRunner(tool_registry={Tools.SMS_TOOL: mock_tool, Tools.CALENDAR_DELETE_TOOL: mock_tool}) #dangerous calendar deletinog tool
    runner.run(task)
    assert task.status==TaskStatus.ESCALATION_PENDING # should be expecting some escalation step
    assert mock_tool.execute.call_count == 1 # should only expect ONCE call!!!!! we are NOT deleting more than one event at a time!!!!


    

def test_runner_raise_tool_not_in_registry():
    steps = [PlanStep(tool=Tools.SMS_TOOL, params={}, status=TaskStatus.PENDING)]
    task = make_task(steps)
    runner= TaskRunner(tool_registry={})
    # empty registry! should expect raised error 
    with pytest.raises(KeyError):
        runner.run(task)

        








