# takes the raw llm output and converts it into ordered plan_steps
# each step is like {tool, params, status} that the worker can execute
from backend.models.datatypes import TaskType, TaskStatus, Tools
from enum import Enum
import json
from datetime import datetime, timezone # UTC time stamp
from typing import Any
from uuid import UUID

# propmt for generating intent. I will factor promptst to another file if they get too much.
INTENT_PROMPT = (
    "You are an intent classifier."
    'Return ONLY JSON: {"intent": "<value>"}'
    "where value is exactly one of: reminder, calendar_update, information_request, morning_digest."


)

MAX_RETRIES = 5

_REQUIRED_PLAN_KEYS = {"task_type", "description", "plan_steps", "response_message"}
_REQUIRED_INTENT_KEYS = {"intent"}


def _missing_keys(raw: dict, required: set) -> set:
    return required - raw.keys()


class PlanStep:
    def __init__(self, tool: Tools | None, params: list|dict, status: TaskStatus):
        self.tool = tool
        self.params= params
        self.status= status

    def __repr__(self):
        # print better when debugging with PlanStep objects
        return f"PlanStep(tool={self.tool}, status={self.status})"

class StructuredTaskPlan:
    def __init__(self, task_type: TaskType, description: str, plan_steps: list[PlanStep], response_message: str):
        self.step_counter =0 
        self.task_type = task_type
        self.description = description
        self.plan_steps = plan_steps 
        self.response_message = response_message
    
    
    
    def current_step(self):
        if self.plan_steps and self.step_counter< len(self.plan_steps):
            return self.plan_steps[self.step_counter]
        else: 
            return None # done or doens' thage steps
    def to_next_step(self) -> int:
        self.step_counter+=1
        if self.step_counter>= len( self.plan_steps):
            return 1 # signals that we are done
        return 0
    def is_done(self) -> bool:
        return self.step_counter>= len( self.plan_steps)
    
    
    def get_type(self):
        return self.task_type
    
    def get_description(self):
        return self.description
    def get_plan_steps(self):
        return self.plan_steps
        
    def get_response_message(self):
        return self.response_message
    def set_response_message(self , new_msg: str):
        self.response_message = new_msg
    
            
        
class Task:
    def __init__(self, id: UUID, user_id: UUID, status: TaskStatus, task_plan: StructuredTaskPlan, escalation_deadline: datetime| None, created_at:datetime, updated_at: datetime) -> None:
        """
        Note: instead of json, I used a list for plan steps since it now makes mor esense to use taht. 
        """
        self.step_counter=0 # incremented by task_runner as steps complete

        self.id = id
        self.user_id = user_id
        self.status = status
        self.task_plan= task_plan
        self.escalation_deadline = escalation_deadline
        self.created_at = created_at
        self.updated_at = updated_at
    
    def mark_complete(self):
        self.status = TaskStatus.COMPLETED

    def get_status(self):
        return self.status
    def get_type(self):
        return self.task_plan.get_type()
    def get_description(self):
        return self.task_plan.get_description()
    def get_plan_steps(self):
        return self.task_plan.get_plan_steps()
    
    # for cleaner code, use getters in the future :
    def get_task_id(self):
        return self.id
    def get_user_id(self):
        return self.user_id
    def get_escalation_deadline(self):
        return self.escalation_deadline
    def get_create_time(self):
        return self.created_at
    def get_last_update_time(self):
        return self.updated_at
    
    def current_step(self):
        return self.task_plan.current_step()
    
    
class TaskPlanner:
    def __init__(self, llm_adapter):
        self.llm_adapter = llm_adapter

    
            
    def create_task_plan(self, query: str, context: dict | str | None = None, intent: TaskType |None = None) -> StructuredTaskPlan:
        # call the llm adapter to get the raw plan
        # depending on the intent type, we might want to create different half manuallly constructed pipelines along with different system prompts to guide the llm to output the right format for each intent
        # for example, if intent is calendar_update, we might want to have a system prompt that specifically tells the llm to output a plan that involves calendar_tool, and we might want to pre-fill some of the params for the calendar_tool based on the context
        # also, the return format would depend on the intent.

        
        task_type = TaskType(intent) if intent else TaskType.INFORMATION_REQUEST
        system_prompt = self._system_prompt_for(task_type)

        try:
            raw = self.llm_adapter.handle(query, system_prompt, context)
            missing = _missing_keys(raw, _REQUIRED_PLAN_KEYS)
            if missing:
                raise ValueError(f"missing required fields: {missing}") # checkfor fields
        except ValueError:
            retry_prompt = system_prompt + f"\n\nExample of a valid response:\n{self._few_shot_example(task_type)}"
            raw = self.llm_adapter.handle(query, retry_prompt, context)
            missing = _missing_keys(raw, _REQUIRED_PLAN_KEYS)
            if missing:
                raise ValueError(f"LLM response missing required fields after retry: {missing}")

        steps = [
            PlanStep(tool=s["tool"], params=s["params"], status=TaskStatus.PENDING) for s in raw.get("plan_steps", [])
        ]
        return StructuredTaskPlan(
            task_type=TaskType(raw["task_type"]),
            description=raw["description"],
            plan_steps=steps,
            response_message=raw["response_message"],
        )

    
    def extract_intent(self, rawText: str, userContext: str):
        """optional helper function to extract the user's intent from the raw text, using the llm adapter. this can be used for routing or other purposes."""

        # given a raw user input, first extract intent, then send to llm to get a plan based on that intent.
        query = (f"Given the user input: '{rawText}' and the user context: '{userContext}',"
                'classify the intent. Return ONLY JSON: {"intent": "<value>"} '
                "where the value is one of: reminder, calendar_update, information_request, morning_digest.")
        # needed to split it for the JSON string 
            
            
        intent_response = self.llm_adapter.handle(query, system_prompt=INTENT_PROMPT) # added system prompt to ensure intent classifier role is clear to the llm
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
        elif intent ==TaskType.CALENDAR_UPDATE:
            return """
            You are a task planner for a personal assistant. The user wants to create, move, reschedule, or delete a calendar event. This is NOT a lookup - it is an action that changes the calendar. 

            Avaliable tools:
            calendar_tool — write/update/delete a calendar event

            Return ONLY valid JSON in this exact shape:

            {
                "task_type": "calendar_update",
                "description": "<one-line summary>",
                "plan_steps": [
                    {
                    "tool": "calendar_tool", 
                    "params": {
                        "action": "update", 
                        "event": "...", 
                        "new_time": "..."}, 
                        "status": "PENDING"
                    }
                ],
                "response_message": "<friendly confirmation to
                send back>"
            }
            """
        elif intent == TaskType.INFORMATION_REQUEST:
            return """
                You are a task planner for a personal assistant. The user wants to look up specific information — a particular email, a single calendar event, or one specific detail. This is NOT a full day summary (that is morning_digest).

                Available tools (use what fits the query):
                    1. gmail_tool — search a specific email
                    2. calendar_tool — look up a specific event
                    3. sms_tool — send the result back to the user

                Return ONLY valid JSON in this exact shape:

                {
                    "task_type": "information_request",
                    "description": "<one-line summary>",
                    "plan_steps": [
                        {
                            "tool": "gmail_tool", 
                            "params": {"query": "from:Sarah", "max_results": 1}, 
                            "status": "PENDING"
                        },
                        {
                            "tool": "sms_tool", 
                            "params": {"message": "<result>"}, 
                            "status": "PENDING"
                        }
                    ],
                    "response_message": "<friendly confirmation to send back>"
                }
            """
        elif intent==TaskType.MORNING_DIGEST:
            return"""
            You are a task planner for a personal assistant. The user wants a full day overview — all calendar events AND important emails for today, compiled into one briefing. This is NOT a specific lookup (that is information_request).

            Available tools (use in this order):
                1. calendar_tool — fetch all of today's events
                2. gmail_tool — fetch important unread emails
                3. sms_tool — send the compiled digest to the user

            Return ONLY valid JSON in this exact shape:

            {
                "task_type": "morning_digest",
                "description": "<one-line summary>",
                "plan_steps": [
                    {
                        "tool": "calendar_tool", 
                        "params": {"date": "today", "max_events": 10}, 
                        "status": "PENDING"
                    },
                    {
                        "tool": "gmail_tool", 
                        "params": {"query": "is:unread", "max_results": 5}, 
                        "status": "PENDING"
                    },
                    {
                        "tool": "sms_tool", 
                        "params": {"message": "<compiled digest>"}, 
                        "status": "PENDING"
                    }
                ],
                "response_message": "<friendly good morning message>"
            }
            """
        else:
            # TODO: for other task types haven't wrote the task description yet need to make up later. 
            return "Not implemented task type."
    # TODO: since I don't think we could assume what llm we are using yet, I can't call specific structural output functions. THis is usually quite effective from previous experience. However, WE SHOULD ADD EXCEPTION HANDLING such as resending query until the shape looks right. 


