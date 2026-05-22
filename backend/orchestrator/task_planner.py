# takes the raw llm output and converts it into ordered plan_steps
# each step is like {tool, params, status} that the worker can execute
from backend.models.datatypes import TaskType, TaskStatus, Tools
from enum import Enum
import json
from datetime import datetime, timezone # UTC time stamp
from typing import Any
from uuid import UUID

class PlanStep:
    def __init__(self, tool: Tools | None, params: list, status: TaskStatus):
        self.tool = tool
        self.params= params
        self.status= status

class StructuredTaskPlan:
    def __init__(self, task_type: TaskType, description: str, plan_steps: list[PlanStep], response_message: str):
        self.step_counter =0 
        self.task_type = task_type
        self.description = description
        self.plan_steps = plan_steps 
        self.response_message = response_message
    
    def set_response_message(self , new_msg: str):
        self.response_message = new_msg
    
    def current_step(self):
        if self.plan_steps and self.step_counter< len(self.plan_steps):
            return self.plan_steps[self.step_counter]
        else: 
            return None # done or doens' thage steps
            
        
class Task:
    def __init__(self, id: UUID, user_id: UUID, status: TaskStatus, type: TaskType, description: str, plan_steps: list[PlanStep], escalation_deadline: datetime| None, created_at:datetime, updated_at: datetime) -> None:
        """
        Note: instead of json, I used a list for plan steps since it now makes mor esense to use taht. 
        """
        self.step_counter=0
        self.id = id
        self.user_id = user_id
        self.status = status
        self.task_plan= StructuredTaskPlan(type, description, plan_steps, "")
        self.escalation_deadline = escalation_deadline
        self.created_at = created_at
        self.updated_at = updated_at
    
    def mark_complete(self):
        self.status = TaskStatus.COMPLETED

    def return_status(self):
        return self.status
    
    def current_step(self):
        return self.task_plan.current_step()
class TaskPlanner:
    def __init__(self, llm_adapter):
        self.llm_adapter = llm_adapter

    
            


    def create_task_plan(self, query: str, context: dict = None, intent: str = None) -> StructuredTaskPlan:
        # call the llm adapter to get the raw plan
        # depending on the intent type, we might want to create different half manuallly constructed pipelines along with different system prompts to guide the llm to output the right format for each intent
        # for example, if intent is calendar_update, we might want to have a system prompt that specifically tells the llm to output a plan that involves calendar_tool, and we might want to pre-fill some of the params for the calendar_tool based on the context
        # also, the return format would depend on the intent.
        raw = self.llm_adapter.handle(query,context)
        steps = [
            PlanStep(tool=s["tool"], params=s["params"], status=TaskStatus.PENDING) for s in raw.get("plan_steps", [])
        ] # extract the steps 
        return StructuredTaskPlan(
            task_type=TaskType(raw["task_type"]),
            description=raw["description"],
            plan_steps=steps,
            response_message = raw["response_message"],
        )




        return None

        
        
    
    def extract_intent(self, rawText: str, userContext: str):
        """optional helper function to extract the user's intent from the raw text, using the llm adapter. this can be used for routing or other purposes."""

        # given a raw user input, first extract intent, then send to llm to get a plan based on that intent.
        query = f"Given the user input: '{rawText}' and the user context: '{userContext}', classify the intent. Return ONLY JSON: {"intent", "<value>"} where the value is one of: reminder, calendar_update, information_request, morning_digest."
        intent_response = self.llm_adapter.handle(query)
        intent = intent_response.get("intent")

        return TaskType(intent) # directly return the intent
    
    def _system_prompt_for(self, intent: TaskType) -> str:
        """
        This is how the planner call the llm for exact steps of calling what tools with what prompts. I think we should consider hardwiring the tool order and only add returned script to the tool from LLM. I will fix this later. Howver, we still need scripts to specify what system prompt is to get the content from LLM """
        if intent == TaskType.REMINDER:
            return """
            You are a task panner for a personal assistant. The user wants to be reminded of something. 

            Avaliable tools (use in this order):
            1. user_pref_tool — fetch the user's preferred contact channel (sms or voice)
            2. script_tool — generate the reminder message with: title, time, context, location
            3. sms_tool — send the script via SMS (use if preferred channel is sms)
            4. phone_call_tool — read the script via voice call (use if preferred channel is voice)

            return ONLY valid JSON in this exact shape:

            {  
                "task_type":"reminder",
                "description":"<one-line summary>",
                “plan_steps":[
                    {"tool": "user_pref_tool", "params": {"user_id": "<user_id>"}, "status": "PENDING"},
                    {"tool": "script_tool", "params": {"title": "...", "time": "...", "context": "...", "location": "..."}, "status": "PENDING"},
                    {"tool": "sms_tool", "params": {"message": "<script from script_tool>"}, "status": "PENDING"} 
                ],
                "response_message": "<friendly SMS confirmation to send back to the user>"

            }

            """
        else:
            # TODO: for other task types haven't wrote the task description yet need to make up later. 
            return "Not implemented task type."
# TODO: since I don't think we could assume what llm we are using yet, I can't call specific structural output functions. THis is usually quite effective from previous experience. However, WE SHOULD ADD EXCEPTION HANDLING such as resending query until the shape looks right. 


