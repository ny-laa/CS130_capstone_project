# [Agent prompt:] Look at backend/workers/task_runner.py and task_runner.py. Write 3 tests for the FULL escalation workflow: 1. When TaskRunner hits a destructive step, theo# orchestrator sends an approval SMS to the parent. 2. When the parent replies "YES" to the approval SMS, the orchestrator rsumes the task: execute descruttive step and the task continues normally. 3. If the parent replies "NO" or doesn't reply within a certain time, the orchestrator cancels the task and the task status is FAILED. You should consult the previous tests to better understand the structure.

# [ellito note] Ensures escalation safety and worksflow. Sees if parent gets the right message, if response from parent handled correctly. The test assumes that ther ewill be literal YES or approve in the returned message, wchi is wrong. We have a button to explicitly approve or deny on the website. I should tell Claude our front end scruture and also the message API structure to test more accurately.

# [Agent prompt:] Update the tests to reflect that the parent will be clicking an "Approve" or "Deny" button on the website, rather than replying with "YES" or "NO". The approval SMS should instruct the parent to click the appropriate button, and the test should check for the presence of these buttons in the message sent to the parent. It it's SMS or Call, the content would be send through an llm, whic interprets the message. This should produce a structured output as well that contains a boolean field "approved". Such call is itself a task step classified as INFORMATION_REQUEST added if we see ESCALATION_PENDING. Additionally, ensure that the test checks for the correct handling of these button clicks in resuming or canceling the task.



from unittest.mock import MagicMock
from backend.orchestrator.orchestrator import GOrchestrator
from backend.workers.task_runner import TaskRunner
from backend.orchestrator.escalation_engine import EscalationEngine
from backend.orchestrator.task_planner import PlanStep, StructuredTaskPlan, Task
from backend.models.datatypes import Tools, TaskStatus, TaskType
from uuid import uuid4
from datetime import datetime, timezone


def make_task(steps):
    plan = StructuredTaskPlan(
        task_type=TaskType.REMINDER,
        description="test",
        plan_steps=steps,
        response_message="ok",
    )
    return Task(
        id=uuid4(),
        user_id=uuid4(),
        status=TaskStatus.PENDING,
        task_plan=plan,
        escalation_deadline=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_request_escalation_approval_sends_app_directed_sms_and_sets_question():
    """
    Orchestrator sends an SMS directing the parent to open the G app to tap
    Approve/Deny (not to reply by text). Also sets task.escalation_question so
    the Tasks dashboard can display it. Destructive step must not have run.
    """
    mock_sms = MagicMock()
    mock_delete = MagicMock()
    steps = [
        PlanStep(tool=Tools.SMS_TOOL, params={"message": "hi"}, status=TaskStatus.PENDING),
        PlanStep(tool=Tools.CALENDAR_DELETE_TOOL, params={"event": "standup"}, status=TaskStatus.PENDING),
    ]
    task = make_task(steps)
    runner = TaskRunner(tool_registry={Tools.SMS_TOOL: MagicMock(), Tools.CALENDAR_DELETE_TOOL: mock_delete})
    runner.run(task)
    assert task.status == TaskStatus.ESCALATION_PENDING

    orch = GOrchestrator(llm_adapter=MagicMock())
    orch.request_escalation_approval(task=task, sms_tool=mock_sms, to="+11234567890")

    mock_sms.execute.assert_called_once()
    call_msg = mock_sms.execute.call_args[0][0]["message"].lower()
    assert "approve" in call_msg or "deny" in call_msg
    assert "app" in call_msg or "open" in call_msg or "g.ai" in call_msg

    assert hasattr(task, "escalation_question")
    assert task.escalation_question

    mock_delete.execute.assert_not_called()


def test_orchestrator_resumes_task_when_approved_true():
    """
    POST /api/tasks/{id}/approve -> backend calls resume_task_from_reply(approved=True).
    Destructive step executes and task status becomes COMPLETED.
    """
    mock_delete = MagicMock()
    steps = [PlanStep(tool=Tools.CALENDAR_DELETE_TOOL, params={"event": "standup"}, status=TaskStatus.PENDING)]
    task = make_task(steps)
    task.status = TaskStatus.ESCALATION_PENDING

    orch = GOrchestrator(llm_adapter=MagicMock())
    orch.resume_task_from_reply(
        task=task,
        approved=True,
        tool_registry={Tools.CALENDAR_DELETE_TOOL: mock_delete},
    )

    mock_delete.execute.assert_called_once()
    assert task.status == TaskStatus.COMPLETED


def test_orchestrator_aborts_task_when_approved_false():
    """
    POST /api/tasks/{id}/deny -> backend calls resume_task_from_reply(approved=False).
    Destructive step must NOT execute and task status becomes FAILED.
    """
    mock_delete = MagicMock()
    steps = [PlanStep(tool=Tools.CALENDAR_DELETE_TOOL, params={"event": "standup"}, status=TaskStatus.PENDING)]
    task = make_task(steps)
    task.status = TaskStatus.ESCALATION_PENDING

    orch = GOrchestrator(llm_adapter=MagicMock())
    orch.resume_task_from_reply(
        task=task,
        approved=False,
        tool_registry={Tools.CALENDAR_DELETE_TOOL: mock_delete},
    )

    mock_delete.execute.assert_not_called()
    assert task.status == TaskStatus.FAILED


def test_parse_approval_response_from_llm_structured_output():
    """
    SMS-reply fallback: LLM interprets the parent's text and returns {"approved": bool}.
    EscalationEngine.parse_approval_response extracts the boolean — the orchestrator
    then passes it as resume_task_from_reply(approved=result["approved"]).
    """
    engine = EscalationEngine()
    assert engine.parse_approval_response({"approved": True}) is True
    assert engine.parse_approval_response({"approved": False}) is False
