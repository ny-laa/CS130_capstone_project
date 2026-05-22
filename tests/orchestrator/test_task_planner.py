from unittest.mock import MagicMock
from backend.orchestrator.task_planner import TaskPlanner
from backend.models.datatypes import TaskType

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
    mock_llm = MagicMock()
    planner = TaskPlanner(mock_llm)
    prompt = planner._system_prompt_for(TaskType.REMINDER) # need this attribute to contaiin following
    assert "sms_tool" in prompt
    assert "plan_steps" in prompt