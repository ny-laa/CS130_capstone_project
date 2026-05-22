# takes the raw llm output and converts it into ordered plan_steps
# each step is like {tool, params, status} that the worker can execute
from backend.models.datatypes import TaskType, TaskStatus
from enum import Enum
import json
from datetime import datetime, timezone # UTC time stamp
from typing import Any
from uuid import UUID


    
class TaskPlanner:
    def __init__(self, llm_adapter):
        self.llm_adapter = llm_adapter


    class StructuredTaskPlan:
        def __init__(self, task_type: TaskType, description: str, plan_steps: list, response_message: str):
            self.task_type = task_type
            self.description = description
            self.plan_steps = plan_steps
            self.response_message = response_message

    class task:
        

        def __init__(self, id: UUID, user_id: UUID, status: TaskStatus, type: str, description: str, plan_steps: list[dict[str, Any]], escalation_deadline: datetime| None, created_at:datetime, updated_at: datetime) -> None:
            """
            Note: instead of json, I used a list for plan steps since it now makes mor esense to use taht. 
            """
            self.id = id
            self.user_id = user_id
            self.status = status
            self.type = type
            self.description = description
            self.plan_steps=plan_steps
            self.escalation_deadline = escalation_deadline
            self.created_at = created_at
            self.updated_at = updated_at
        
        def change_status(self, new_stat:Status):
            # TODO: no guard unsafe should change
            self.status = new_stat



            
            

    def create_task_plan(self, query: str, context: dict = None, intent: str = None) -> list:
        # call the llm adapter to get the raw plan
        # depending on the intent type, we might want to create different half manuallly constructed pipelines along with different system prompts to guide the llm to output the right format for each intent
        # for example, if intent is calendar_update, we might want to have a system prompt that specifically tells the llm to output a plan that involves calendar_tool, and we might want to pre-fill some of the params for the calendar_tool based on the context
        # also, the return format would depend on the intent.
        return None

        
        
    
    def extract_intent(self, rawText: str, userContext: str):
        """optional helper function to extract the user's intent from the raw text, using the llm adapter. this can be used for routing or other purposes."""

        # given a raw user input, first extract intent, then send to llm to get a plan based on that intent.
        query = f"Given the user input: '{rawText}' and the user context: '{userContext}', what is the user's intent? Respond with one and only one of: reminder, calendar_update, information_request, morning_digest."
        intent_response = self.llm_adapter.handle(query)
        intent = intent_response.get("intent")

        return TaskType(intent) # directly return the intent

