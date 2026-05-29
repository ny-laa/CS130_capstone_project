from backend.orchestrator.escalation_engine import EscalationEngine
from backend.orchestrator.task_planner.import PlanStep
from backend.models.datatypes import TaskStatus

def test_needs_escalation_true_for_destructive_tool():
    engine = EscalationEngine()
    steps = [PlanStep(tool="calandar_delete_tool", params={}, status=TaskStatus.PENDING)] # deleting an event is dangerous. needs user confirm
    assert engine.needs_escalation(steps) is True


def test_needs_escalation_false_for_safe_tool():
    engine = EscalationEngine()
    steps = [PlanStep(tool="sms_tool", params={}, status=TaskStatus.PENDING)] # for now we consider sending sms safe by oru llm decisions
    assert engine.needs_escalation(steps) is False

