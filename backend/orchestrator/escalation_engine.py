# figures out when G needs to pause and ask the parent for approval
# high-risk actions like deleting calendar events shouldnt just happen automatically
from backend.models.datatypes import Tools
from backend.orchestrator.task_planner import PlanStep


DESCRUCTIVE_TOOLS={
    Tools.CALENDAR_DELETE_TOOL,

    # add more as we discuss what is dangerous
    
}

class EscalationEngine:
    def __init__(self) -> None:
        self.llm = None 
    def task_needs_escalation(self, steps: list) -> bool:
        # check if anytool in the whole task is dangerous. 
        return any(step.tool in DESCRUCTIVE_TOOLS for step in steps)
    
    def step_needs_escalation(self, step: PlanStep) -> bool:
        # check if anytool in the step is dangerous.
        return step.tool in DESCRUCTIVE_TOOLS

    def parse_approval_response(self, llm_output: dict) -> bool:
        # extracts the boolean from LLM structured output {"approved": bool}
        # used when parent replies by SMS/call instead of clicking the app button
        # same structued filed for both ;)
        return bool(llm_output.get("approved", False))
    


    
    
    


