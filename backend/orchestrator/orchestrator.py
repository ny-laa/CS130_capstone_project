# this is basically the brain of the whole system
# GOrchestrator: takes a task from the user, builds a plan, dispatches to the right tools
# also handles escalation when G needs human approval before doing something

from backend.adapters.llm.claude_adapter import ClaudeAdapter
from backend.models.datatypes import TaskType, TaskStatus
from backend.orchestrator.task_planner import TaskPlanner, Task
from backend.orchestrator.escalation_engine import EscalationEngine
from backend.workers.task_runner import TaskRunner
from datetime import datetime, timezone

from uuid import UUID, uuid4


# [AI prompt]: generate a Planner system prompt that forces claude to return a JSON plan with fields task_type, description, plan_steps (list of tool, params, status), and response_message. The prompt should make it clear that the LLM should NOT try to execute any steps itself, only return the plan. Available tools are sms_tool, calendar_tool, gmail_tool, call_tool, script_tool, user_pref_tool. The task types can be reminder, calendar_update, information_request, morning_digest. The response_message is a short friendly confirmation to send back to the parent after the plan is created.

#[ellito note] This is clear and uses the same schema as before. I will jsut use it in the handle function 

_PLANNER_SYSTEM_PROMPT = """You are G, a task-planning AI for a personal assistant app.
Your ONLY job is to produce a JSON execution plan. You do NOT send messages, set reminders,
or take any action yourself — a separate worker will execute each step you specify.

Return ONLY valid JSON, no other text:
{
    "task_type": "<one of: reminder, calendar_update, information_request, morning_digest>",
    "description": "<one-line summary of what the parent is asking for>",
    "plan_steps": [
        {"tool": "<tool name>", "params": {}, "status": "PENDING"}
    ],
    "response_message": "<short friendly confirmation to send back to the parent>"
}

Available tools: sms_tool, calendar_tool, gmail_tool, call_tool, script_tool, user_pref_tool"""


class GOrchestrator:

    def __init__(self, llm_adapter=None):
        # default to claude but you can swap in gpt or anything else thats a BaseLLMAdapter
        self.llm = llm_adapter or ClaudeAdapter()

    def handle(self, query: str, context: dict = None) -> dict:
        # just pass the query straight to the llm adapter
        # context is optional (e.g. calendar events, user prefs)
        return self.llm.handle(query, _PLANNER_SYSTEM_PROMPT, context)

    def delegate_task(self, message: str, user_id: UUID, context: dict |None = None) -> Task:
        # main entry point from the webhook handlers
        # creates a plan and returns it with user_id and PENDING status
        # TODO: actually persist this to the tasks table once db is wired up
        # TODO: decide how the context is built from external database given user ID. 

        
        planner = TaskPlanner(self.llm)
        task_intent = planner.extract_intent(message, str(context)) # need to make context into string
        
        plan = planner.create_task_plan(message, context, task_intent)

        task = Task(
            id =uuid4(), # task id, how to make unique?
            user_id=user_id,
            status=TaskStatus.PENDING,
            task_plan=plan,
            escalation_deadline=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        return task
    

    def request_escalation_approval(self, task: Task, sms_tool, to: str) -> None:
        # when G needs approval from the parent to execute a step send an SMS to notify parent
        step = task.task_plan.current_step()


        result = step.result  # returns None if step doesn't have a result attribute (NOT False unless we specify it. safe ;) 
        if isinstance(result, dict) and result.get("available") is False and result.get("busy_windows"):
            busy = result["busy_windows"]
            conflict_str = f"{busy[0]['start']} to {busy[0]['end']}" if busy else "that time"
            question = f"There's a scheduling conflict: you're busy from {conflict_str}. Open the G app to Approve (add anyway) or Deny."
        else:
            question = f"G needs your approval to run {step.tool}. Open the G app to Approve or Deny."
        task.escalation_question = question
        sms_tool.execute({"to": to, "message": question})

    def resume_task_from_reply(self, task: Task, approved: bool, tool_registry: dict) -> None:
        if not approved:
            # parent clicked deny, early return!
            task.status = TaskStatus.FAILED
            return
        
        # parent approved, resume task ;)
        step = task.task_plan.current_step()
        # if the parent approved despite a calendar conflict, record it on the task and
        # inject force_overlap into the next write step's params so the calendar tool can skip its own guard
        if isinstance(step.result, dict) and step.result.get("available") is False:
            task.force_overlap = True
            next_step = task.task_plan.plan_steps[task.task_plan.step_counter + 1] if task.task_plan.step_counter + 1 < len(task.task_plan.plan_steps) else None
            if next_step:
                next_step.params["force_overlap"] = True
        adapter = tool_registry.get(step.tool)
        if adapter is None:
            raise KeyError(f"No adapter for tool: {step.tool}")
        adapter.execute(step.params)
        step.status = TaskStatus.COMPLETED
        task.task_plan.to_next_step()
        runner = TaskRunner(tool_registry=tool_registry)
        runner.run(task)

    def handle_incoming_message(self, userID: UUID, rawText: str) -> None:
        # call cases
        # TODO: two-way conversation handling
        pass


