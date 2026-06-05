from models.datatypes import TaskType, TaskStatus, Tools
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

# required top-level keys for every plan response
_REQUIRED_PLAN_KEYS = {"task_type", "description", "plan_steps", "response_message"}
_REQUIRED_INTENT_KEYS = {"intent"}

# incase we have to add some extra fields in the future for speficic task types (such as calendar adding)
_REQUIRED_PLAN_KEYS_BY_TYPE: dict = {
    TaskType.REMINDER:            _REQUIRED_PLAN_KEYS,
    TaskType.CALENDAR_UPDATE:     _REQUIRED_PLAN_KEYS,
    TaskType.INFORMATION_REQUEST: _REQUIRED_PLAN_KEYS,
    TaskType.MORNING_DIGEST:      _REQUIRED_PLAN_KEYS,
}


def _missing_keys(raw: dict, required: set) -> set:
    return required - raw.keys()


class PlanStep:
    def __init__(self, tool: Tools | None, params: list|dict, status: TaskStatus):
        self.tool = tool
        self.params= params
        self.status= status
        self.result = None  # populated by TaskRunner after adapter.execute(), only False if we deliberately set it when step is unavaliable. 

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
        # Note: instead of json, I used a list for plan steps since it now makes mor esense to use taht. 
        
        self.step_counter=0 # incremented by task_runner as steps complete
        self.force_overlap = False  # set to True when parent approves adding an event despite a calendar conflict

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
        few_shot_prompt = system_prompt + f"\n\nExample of a valid response:\n{self._few_shot_example(task_type)}"

        # try until MAX_RETRIEs time if the returned llm otuput is in the wrong format or missing keys

        for attempt in range(MAX_RETRIES):
            current_prompt = system_prompt if attempt == 0 else few_shot_prompt
            try:
                raw = self.llm_adapter.handle(query, current_prompt, context)  # raises ValueError if not JSON
                if not isinstance(raw, dict):
                    raise ValueError(f"LLM returned non-dict JSON: {type(raw)}")
                missing = _missing_keys(raw, _REQUIRED_PLAN_KEYS_BY_TYPE.get(task_type, _REQUIRED_PLAN_KEYS))
                if not missing:
                    break
                raise ValueError(f"missing required fields: {missing}")
            except ValueError as e:
                if attempt == MAX_RETRIES - 1:
                    raise ValueError(f"LLM response missing required fields after {MAX_RETRIES} retries: {e}")

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
            
            
        few_shot_query = query + '\n\nReturn ONLY: {"intent": "<value>"}'

        for attempt in range(MAX_RETRIES):
            current_query = query if attempt == 0 else few_shot_query
            try:
                intent_response = self.llm_adapter.handle(current_query, system_prompt=INTENT_PROMPT)
                if not _missing_keys(intent_response, _REQUIRED_INTENT_KEYS):
                    break
                raise ValueError("missing intent field")
            except ValueError as e:
                # either from parsing llm response as JSON or from msising fields. Retry
                if attempt == MAX_RETRIES - 1:
                    raise ValueError(f"LLM intent response invalid after {MAX_RETRIES} retries: {e}")

        return TaskType(intent_response["intent"])
    



    # [prompt:] Look at the create_task_plan function and teh test file under tests/orchestrator/test_task_planner.py. Understand where we call the LLM to get the plan steps. We want to make sure the LLM outputs the right format, so we check for required fields and retry with a few-shot example if the format is wrong. Generate a few shot examples for each intent type so that the llm can use it as reference. The system prompt should guide the LLM to output the right tools and params for each intent, and the few-shot example should show a valid JSON response for that intent. 

    # [eliot note] It's clear from my test filed and prompts how to format the response, the examples are straighforward and fits our expectations. 
    def _few_shot_example(self, intent: TaskType) -> str:
        # examples for how the planner llm would respond to intents. shows the format
        examples = {
            TaskType.REMINDER: '{"task_type":"reminder","description":"Pick up kids at 3pm","plan_steps":[{"tool":"user_pref_tool","params":{"user_id":"abc"},"status":"PENDING"},{"tool":"script_tool","params":{"title":"Pick up kids","time":"3pm","context":"","location":"school"},"status":"PENDING"},{"tool":"sms_tool","params":{"message":"Reminder: pick up kids at 3pm"},"status":"PENDING"}],"response_message":"Got it! Reminding you at 3pm."}',
            TaskType.CALENDAR_UPDATE: '{"task_type":"calendar_update","description":"Move standup to 4pm","plan_steps":[{"tool":"calendar_tool","params":{"operation":"check_availability","start_time":"<ISO>","end_time":"<ISO>"},"status":"PENDING"},{"tool":"calendar_tool","params":{"operation":"write","action":"update","event":"standup","new_time":"4pm"},"status":"PENDING"}],"response_message":"Let me check your calendar first, then move the standup."}',
            TaskType.INFORMATION_REQUEST: '{"task_type":"information_request","description":"Find latest email from Sarah","plan_steps":[{"tool":"gmail_tool","params":{"query":"from:Sarah","max_results":1},"status":"PENDING"},{"tool":"sms_tool","params":{"message":"<result>"},"status":"PENDING"}],"response_message":"Looking it up now!"}',
            TaskType.MORNING_DIGEST: '{"task_type":"morning_digest","description":"Daily morning briefing","plan_steps":[{"tool":"calendar_tool","params":{"date":"today","max_events":10},"status":"PENDING"},{"tool":"gmail_tool","params":{"query":"is:unread","max_results":5},"status":"PENDING"},{"tool":"sms_tool","params":{"message":"<digest>"},"status":"PENDING"}],"response_message":"Good morning! Here is your digest."}',
        }
        return examples.get(intent, "")

    def _system_prompt_for(self, intent: TaskType) -> str:
        
        # This is how the planner call the llm for exact steps of calling what tools with what prompts. I think we should consider hardwiring the tool order and only add returned script to the tool from LLM. I will fix this later. Howver, we still need scripts to specify what system prompt is to get the content from LLM




        if intent == TaskType.REMINDER:
            return """
            You are a task panner for a personal assistant. The user wants to be reminded of something. 

            Prepended information about the user's family member and contacts is avaliable. Use that to fill in any missing details in the plan, such as who the event is with or where it is.

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
            You are a task planner for a personal assistant. The user wants to create, move, reschedule, or delete a calendar event. This is NOT a lookup — it is an action that changes the calendar.

            Prepended information about the user's family member and contacts is avaliable. Use that to fill in any missing details in the plan, such as who the event is with or where it is.

            IMPORTANT: For any write (create/update/move), ALWAYS include a check_availability step FIRST. The worker will pause and ask the parent if there is a conflict — do NOT skip this step.

            Available tools (use in this order for writes):
            1. calendar_tool with operation "check_availability" — check if the time slot is free
            2. calendar_tool with operation "write" — create/update/move/delete the event

            CRITICAL: For calendar_tool steps, ALWAYS use exactly these param names:
            - "operation": one of "check_availability", "read", or "write"  
            - "start_time": ISO 8601 datetime string (e.g. "2026-06-05T17:00:00-07:00")
            - "end_time": ISO 8601 datetime string
            Never use check_time, query_time, target_time, or any other variation.

            Return ONLY valid JSON in this exact shape:

            {
                "task_type": "calendar_update",
                "description": "<one-line summary>",
                "plan_steps": [
                    {"tool": "calendar_tool", "params": {"operation": "check_availability", "start_time": "<ISO 8601>", "end_time": "<ISO 8601>"}, "status": "PENDING"},
                    {"tool": "calendar_tool", "params": {"operation": "write", "action": "create", "summary": "...", "start_time": "<ISO 8601>", "end_time": "<ISO 8601>"}, "status": "PENDING"}
                ],
                "response_message": "<friendly confirmation to send back>"
            }
            """
        elif intent == TaskType.INFORMATION_REQUEST:
            return """
                You are a task planner for a personal assistant. The user wants to look up specific information — a particular email, a single calendar event, or one specific detail. This is NOT a full day summary (that is morning_digest).

                Prepended information about the user's family member and contacts is avaliable. Use that to fill in any missing details in the plan, such as who the event is with or where it is.

                Available tools (use what fits the query):
                    1. gmail_tool — search a specific email
                    2. calendar_tool — look up a specific event
                    3. sms_tool — send the result back to the user

                CRITICAL: For calendar_tool steps, ALWAYS use exactly these param names:
                - "operation": one of "check_availability", "read", or "write"  
                - "start_time": ISO 8601 datetime string (e.g. "2026-06-05T17:00:00-07:00")
                - "end_time": ISO 8601 datetime string
                Never use check_time, query_time, target_time, or any other variation.

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

            Prepended information about the user's family member and contacts is avaliable. Use that to fill in any missing details in the plan, such as who the event is with or where it is.

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


