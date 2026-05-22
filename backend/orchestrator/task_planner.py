# takes the raw llm output and converts it into ordered plan_steps
# each step is like {tool, params, status} that the worker can execute
from backend.models.datatypes import TaskType

class TaskPlanner:
    def __init__(self, llm_adapter):
        self.llm_adapter = llm_adapter
    
    class StructuredTaskPlan:
        def __init__(self, task_type: TaskType, description: str, plan_steps: list, response_message: str):
            self.task_type = task_type
            self.description = description
            self.plan_steps = plan_steps
            self.response_message = response_message
            

    def create_task_plan(self, query: str, context: dict = None, intent: str = None) -> list:
        # call the llm adapter to get the raw plan
        # depending on the intent type, we might want to create different half manuallly constructed pipelines along with different system prompts to guide the llm to output the right format for each intent
        # for example, if intent is calendar_update, we might want to have a system prompt that specifically tells the llm to output a plan that involves calendar_tool, and we might want to pre-fill some of the params for the calendar_tool based on the context
        # also, the return format would depend on the intent.

        
        
    
    def extract_intent(self, awText: str, userContext: str):
        """optional helper function to extract the user's intent from the raw text, using the llm adapter. this can be used for routing or other purposes."""

        # given a raw user input, first extract intent, then send to llm to get a plan based on that intent.
        query = f"Given the user input: '{rawText}' and the user context: '{userContext}', what is the user's intent? Respond with one of: reminder, calendar_update, information_request, morning_digest."
        intent_response = self.llm_adapter.handle(query)
        intent = intent_response.get("intent")


        return create_task_plan(query=rawText, context={"user_context": userContext}, intent=intent)
