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


def test_live_delegate_task():
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("no key")
    
    orch = GOrchestrator()
    fake_user_id = uuid4()
    result = orch.delegate_task("Remind me to pick up Emma and Max from school at 3 pm", fake_user_id)

    print("delegate task live test output:")
    print("type:", result.get_type())
    print("status:", result.get_status())
    print("steps:", result.get_plan_steps())
    print("response:", result.task_plan.get_response_message())

    assert result.get_type()== TaskType.REMINDER
    assert result.get_status() == TaskStatus.PENDING
    assert len(result.get_plan_steps()) > 0 # MUST have some step!!!
    assert len(result.task_plan.get_response_message())> 0 # would expect some resposne message. 




# I'm adding more tests using AI since writing them myself is too slow, and I want to test similar concepts with differnt values. 

# [AI Agent Prompt] Look at the code in backend/orchestrator, and look at the tests under tests/orchestrator/test_task_planner.py. Write 5 more tests that mock the interaction with real life Claude    using different task types. For instance, you can replace the reminder in TaskType to CALENDAR_UPDATE. The 5 tesets should span across all 4 task types: REMINDER, CALENDAR_UPDATE, INFORMATION_REQUEST, MORNING_DIGEST    

# [Elliot's Note] these tests mirrors the correct format as before. They also came up with creative design of steps and check if the planner correctly stores them. The issue it, AI missed my intent to create LIVE test with Claude back end. I will ask it to add them 


def test_create_task_plan_reminder_multi_step():
    """mock: full reminder pipeline — user_pref_tool → script_tool → sms_tool"""
    mock_llm = MagicMock()
    mock_llm.handle.return_value = {
        "task_type": "reminder",
        "description": "Pick up groceries at 5pm",
        "plan_steps": [
            {"tool": "user_pref_tool", "params": {"user_id": "abc"}, "status": "PENDING"},
            {"tool": "script_tool", "params": {"title": "Groceries", "time": "5pm", "context": "", "location": "store"}, "status": "PENDING"},
            {"tool": "sms_tool", "params": {"message": "Don't forget groceries at 5pm!"}, "status": "PENDING"},
        ],
        "response_message": "Got it, I'll remind you at 5pm.",
    }
    planner = TaskPlanner(mock_llm)
    plan = planner.create_task_plan("Remind me to pick up groceries at 5pm", intent="reminder")

    assert plan.task_type == TaskType.REMINDER
    assert len(plan.plan_steps) == 3
    assert plan.plan_steps[0].tool == "user_pref_tool"
    assert plan.plan_steps[1].tool == "script_tool"
    assert plan.plan_steps[2].tool == "sms_tool"
    assert "5pm" in plan.response_message


def test_extract_intent_returns_calendar_update():
    """mock: LLM classifies a meeting reschedule request as calendar_update"""
    mock_llm = MagicMock()
    mock_llm.handle.return_value = {"intent": "calendar_update"}
    planner = TaskPlanner(mock_llm)
    result = planner.extract_intent("Move my 3pm standup to 4pm", "user has google calendar")
    assert result == TaskType.CALENDAR_UPDATE


def test_create_task_plan_calendar_update():
    """mock: calendar_update plan uses calendar_tool then confirms via sms"""
    mock_llm = MagicMock()
    mock_llm.handle.return_value = {
        "task_type": "calendar_update",
        "description": "Reschedule standup from 3pm to 4pm",
        "plan_steps": [
            {"tool": "calendar_tool", "params": {"event": "standup", "old_time": "3pm", "new_time": "4pm"}, "status": "PENDING"},
            {"tool": "sms_tool", "params": {"message": "Your standup has been moved to 4pm."}, "status": "PENDING"},
        ],
        "response_message": "Done! Standup moved to 4pm.",
    }
    planner = TaskPlanner(mock_llm)
    plan = planner.create_task_plan("Move my standup to 4pm", intent="calendar_update")

    assert plan.task_type == TaskType.CALENDAR_UPDATE
    assert plan.plan_steps[0].tool == "calendar_tool"
    assert plan.plan_steps[0].params["new_time"] == "4pm"
    assert plan.response_message == "Done! Standup moved to 4pm."


def test_create_task_plan_information_request():
    """mock: information_request queries gmail then summarizes and texts result"""
    mock_llm = MagicMock()
    mock_llm.handle.return_value = {
        "task_type": "information_request",
        "description": "Find latest email from Sarah",
        "plan_steps": [
            {"tool": "gmail_tool", "params": {"query": "from:Sarah", "max_results": 1}, "status": "PENDING"},
            {"tool": "script_tool", "params": {"summary": "latest email from Sarah"}, "status": "PENDING"},
            {"tool": "sms_tool", "params": {"message": "<summary from script_tool>"}, "status": "PENDING"},
        ],
        "response_message": "I'll look that up and text you what I find.",
    }
    planner = TaskPlanner(mock_llm)
    plan = planner.create_task_plan("What did Sarah last email me about?", intent="information_request")

    assert plan.task_type == TaskType.INFORMATION_REQUEST
    assert len(plan.plan_steps) == 3
    assert plan.plan_steps[0].tool == "gmail_tool"
    assert plan.plan_steps[0].params["query"] == "from:Sarah"
    assert "look that up" in plan.response_message


def test_create_task_plan_morning_digest():
    """mock: morning_digest aggregates calendar + gmail into a single sms briefing"""
    mock_llm = MagicMock()
    mock_llm.handle.return_value = {
        "task_type": "morning_digest",
        "description": "Daily morning briefing",
        "plan_steps": [
            {"tool": "calendar_tool", "params": {"date": "today", "max_events": 5}, "status": "PENDING"},
            {"tool": "gmail_tool", "params": {"query": "is:unread", "max_results": 5}, "status": "PENDING"},
            {"tool": "script_tool", "params": {"briefing": "calendar + email summary"}, "status": "PENDING"},
            {"tool": "sms_tool", "params": {"message": "<briefing from script_tool>"}, "status": "PENDING"},
        ],
        "response_message": "Good morning! Here's your daily briefing.",
    }
    planner = TaskPlanner(mock_llm)
    plan = planner.create_task_plan("Give me my morning digest", intent="morning_digest")

    assert plan.task_type == TaskType.MORNING_DIGEST
    assert len(plan.plan_steps) == 4
    assert plan.plan_steps[0].tool == "calendar_tool"
    assert plan.plan_steps[1].tool == "gmail_tool"
    assert plan.plan_steps[3].tool == "sms_tool"
    assert "morning" in plan.response_message.lower()



# [AI Agent Prompt] the tests you wrote are testing static properties of the Planner. I want you to add LIVE tests that calles the Claude Adapter to retrieve actual planned stteps decided by Claude. This will be used at scale in production, and you should print the result as I did, but not forcefully expect the steps to be in any particular order. DO NOT MODIFY ANY OF THE ABOVE CODE OR COMMENTS. Start below.

# [elliot's Note] Now this looks right. They are mirroring what I wrote at scale. These found many bugs! Claude doesn't return a structured output for some of them. So we really need to add the resend loop if Json is not detected.

# some tricky cases are that AI classified "Give me my morning digest for today", intent="morning_digest" as INFORMATION_REQUESTION. We need better definitions of each case that clearly distincts the boundary. 

def test_live_create_task_plan_reminder_multi_step():
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("no key")
    planner = TaskPlanner(ClaudeAdapter())
    plan = planner.create_task_plan("Remind me to pick up groceries at 5pm", intent="reminder")
    print("live reminder multi-step output:")
    print("type:", plan.task_type)
    print("steps:", plan.plan_steps)
    print("response:", plan.response_message)
    assert plan.task_type == TaskType.REMINDER
    assert len(plan.plan_steps) > 0
    assert len(plan.response_message) > 0


def test_live_create_task_plan_calendar_update():
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("no key")
    planner = TaskPlanner(ClaudeAdapter())
    plan = planner.create_task_plan("Move my 3pm standup to 4pm tomorrow", intent="calendar_update")
    print("live calendar_update output:")
    print("type:", plan.task_type)
    print("steps:", plan.plan_steps)
    print("response:", plan.response_message)
    assert plan.task_type == TaskType.CALENDAR_UPDATE
    assert len(plan.plan_steps) > 0
    assert len(plan.response_message) > 0


def test_live_create_task_plan_information_request():
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("no key")
    planner = TaskPlanner(ClaudeAdapter())
    plan = planner.create_task_plan("What did Sarah last email me about?", intent="information_request")
    print("live information_request output:")
    print("type:", plan.task_type)
    print("steps:", plan.plan_steps)
    print("response:", plan.response_message)
    assert plan.task_type == TaskType.INFORMATION_REQUEST
    assert len(plan.plan_steps) > 0
    assert len(plan.response_message) > 0


def test_live_create_task_plan_morning_digest():
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("no key")
    planner = TaskPlanner(ClaudeAdapter())
    plan = planner.create_task_plan("Give me my morning digest for today", intent="morning_digest")
    print("live morning_digest output:")
    print("type:", plan.task_type)
    print("steps:", plan.plan_steps)
    print("response:", plan.response_message)
    assert plan.task_type == TaskType.MORNING_DIGEST
    assert len(plan.plan_steps) > 0
    assert len(plan.response_message) > 0


def test_live_extract_intent_information_request():
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("no key")
    planner = TaskPlanner(ClaudeAdapter())
    result = planner.extract_intent("What time does my dentist appointment start?", "user has calendar and email access")
    print("live intent extraction output:")
    print("intent:", result)
    assert result == TaskType.INFORMATION_REQUEST




#####################
# adding more test now to isolate the issue

def test_live_extract_intent_morning_digest():
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("no key")
    planner= TaskPlanner(ClaudeAdapter())
    result = planner.extract_intent("Give me my morning digest for today", "no context")
    assert result == TaskType.MORNING_DIGEST


def test_create_task_plan_retries_on_missing_fields():
    # now added test no missing response field case from planner. we shoudl detect this and retry sending the quewry 
    mock_llm = MagicMock()
    mock_llm.handle.side_effect = [
        {"task_type": "reminder"},  # first call: missing fields
        {
            "task_type": "reminder",
            "description": "Call Lucy at 3pm",
            "plan_steps": [{"tool": "sms_tool", "params": {"message": "Call Lucy"}, "status": "PENDING"}],
            "response_message": "Got it!",
        },
    ]
    planner = TaskPlanner(mock_llm)
    plan = planner.create_task_plan("Remind me to call Lucy at 3pm", intent="reminder")

    assert plan.task_type == TaskType.REMINDER
    assert mock_llm.handle.call_count == 2



def test_create_task_plan_retries_on_wrong_format():
    # wrong format not json
    mock_llm = MagicMock()
    mock_llm.handle.side_effect = [
        {"Yes, I'm happy to remind you to call lucy at 3 pm! I will add tshi to your calenar ;)"},  # first call: wrong format
        {
            "task_type": "reminder",
            "description": "Call Lucy at 3pm",
            "plan_steps": [{"tool": "sms_tool", "params": {"message": "Call Lucy"}, "status": "PENDING"}],
            "response_message": "Got it!",
        },
    ]
    planner = TaskPlanner(mock_llm)
    plan = planner.create_task_plan("Remind me to call Lucy at 3pm", intent="reminder")

    assert plan.task_type == TaskType.REMINDER
    assert mock_llm.handle.call_count == 2 # second response is leagal 

def test_create_task_plan_raises_after_max_retries():
    mock_llm = MagicMock()
    mock_llm.handle.return_value = {"task_type": "reminder"}  # always missing fields

    planner = TaskPlanner(mock_llm)
    with pytest.raises(ValueError, match="missing required fields"):
        planner.create_task_plan("Remind me to call Lucy at 3pm", intent="reminder")
        # give up after max try.. go to human support. 


# new test: live to calude to see if we cehcks teh right avalibailtiy from a calendar. 
def test_live_calendar_update_plan_includes_availability_check():
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("no key")
    planner = TaskPlanner(ClaudeAdapter())
    plan = planner.create_task_plan("Add picking up Mary from school to my calendar at 5pm tomorrow", intent="calendar_update")
    print("live calendar_update conflict-check output:")
    print("type:", plan.task_type)
    print("steps:", plan.plan_steps)
    print("response:", plan.response_message)

    assert plan.task_type == TaskType.CALENDAR_UPDATE
    assert len(plan.plan_steps) >= 2  # must have at least check + write

    tools_in_plan = [str(s.tool) for s in plan.plan_steps]
    assert tools_in_plan[0] == "calendar_tool"  # check step must be first

    first_step_params = plan.plan_steps[0].params
    assert first_step_params.get("operation") == "check_availability"  # must be a check, not a write

