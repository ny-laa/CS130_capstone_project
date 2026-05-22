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
    
