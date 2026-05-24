from unittest.mock import MagicMock, patch
from backend.orchestrator.task_planner import TaskPlanner, StructuredTaskPlan
from backend.orchestrator.orchestrator import GOrchestrator
from backend.models.datatypes import TaskType, TaskStatus
import os 
from backend.adapters.llm.claude_adapter import ClaudeAdapter
from uuid import uuid4
import pytest


# for Claude live testing
from dotenv import load_dotenv
load_dotenv("backend/.env")

"""
all the tests for task planner nwo
"""

def test_extract_intent_returns_reminder():
    """
    test if we could return the extracted intnet corerctly if our LLM correctly responded
    for now, use fake llm backend
    """
    mock_llm = MagicMock()
    mock_llm.handle.return_value={
        "intent": "reminder" 
    }
    planner = TaskPlanner(mock_llm)
    result = planner.extract_intent("Remind me to call Lucy at 3 pm", "no conext")
    assert result == TaskType.REMINDER
    

def test_system_prompt_for_reminder_mentions_sms_tool():
    """ we shoudl probably not test hardcoded properties in the future. for now, we will asusme llm returns perfect json as requsted. in the future if we change the prompt we should change this test"""
    mock_llm = MagicMock()
    planner = TaskPlanner(mock_llm)
    prompt = planner._system_prompt_for(TaskType.REMINDER) # need this attribute to contaiin following
    assert "sms_tool" in prompt
    assert "plan_steps" in prompt


def test_create_task_plan_returns_given_plan():
    """if we are given a correct plan, w should return its results correctly"""

    mock_llm = MagicMock()
    mock_llm.handle.return_value = {
        "task_type": "reminder",
        "description": "Call Lucy at 3pm",
        "plan_steps": [
            {"tool": "sms_tool", "params": {"message":"Call Lucy"}, "status": "PENDING"}],"response_message": "Got it, I'll remind you at 3pm.",
    }
    planner = TaskPlanner(mock_llm)
    plan = planner.create_task_plan("Remind me to call Lucy at 3pm", intent="reminder")

    assert plan.task_type == TaskType.REMINDER
    assert len(plan.plan_steps) == 1
    assert plan.plan_steps[0].tool == "sms_tool"
    assert plan.response_message == "Got it, I'll remind you at 3pm."

def test_live_create_task_plan():
    assert os.getenv("ANTHROPIC_API_KEY")
    
    planner = TaskPlanner(ClaudeAdapter())

    plan = planner.create_task_plan("Remind me to call Max at 1pm to have a beer with him", intent="reminder")

    print("plan output check:")
    print(plan.task_type, plan.plan_steps,plan.response_message)
    assert plan.task_type == TaskType.REMINDER
    assert len(plan.plan_steps)>0



def test_live_extract_intent_reminder():
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("no key") # need key to run test correctly
    planner = TaskPlanner(ClaudeAdapter())
    result = planner.extract_intent("Remind me to call Mark at 6pm for food", "no context")
    assert result==TaskType.REMINDER # should get the right task type

def test_live_extract_intent_calendar():
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("no key") # need key to run test correctly
    planner = TaskPlanner(ClaudeAdapter())
    result = planner.extract_intent("Move my 2pm meeting to 4pm", "no context")
    assert result==TaskType.CALENDAR_UPDATE # should get the right task type




def test_delegate_task_uses_planner():
    # it's too strict to mock llm return behavior in order since we could add additional retries or info requests later. I will just mock the planner here.
    fake_plan= StructuredTaskPlan(
        task_type=TaskType.REMINDER,
        description="Call Macy at 6:30pm",
        plan_steps=[],
        response_message="Got it! (from hardwired planner)"
    ) 
    # swap out the planner inside orchestrator iwth our hardwaried palnener
    with patch("backend.orchestrator.orchestrator.TaskPlanner") as MockPlanner:
        fake_planner = MagicMock()
        fake_planner.extract_intent.return_value = TaskType.REMINDER
        fake_planner.create_task_plan.return_value = fake_plan
        # this is statically set, and we only test if the orchestrator calls the right funcitosn in planner and the panner gets the resutls right. 
        MockPlanner.return_value=fake_planner
        fake_user_id=uuid4()
        orch = GOrchestrator(llm_adapter=MagicMock())
        result = orch.delegate_task("Remind me to call Macy", user_id=fake_user_id) # made up test, time from response should either be infered from google calendar or INFORMATION REQUEST to clarify it

    # returned structured otuput should contain the right info. If result is not a JOSN, that means our error handling routine is no implemented or made a mistake. 
    assert result.get_type() == TaskType.REMINDER
    assert result.get_status()== TaskStatus.PENDING
    assert result.user_id == fake_user_id # should match the one we got. 










