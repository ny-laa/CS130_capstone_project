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
class GOrchestrator:

    def __init__(self, llm_adapter=None):
        # default to claude but you can swap in gpt or anything else thats a BaseLLMAdapter
        self.llm = llm_adapter or ClaudeAdapter()

    def handle(self, query: str, context: dict = None) -> dict:
        # just pass the query straight to the llm adapter
        # context is optional (e.g. calendar events, user prefs)
        # for now systemp prompt "", figure out later
        return self.llm.handle(query, "", context)

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
        # we could change up the prompt to more specific or friendly if we want, but the idea is to ask the parent to approve or deny the escalation by clicking teh button of approvala
        step = task.task_plan.current_step()
        question= f"G needs your approval to run {step.tool} with params {step.params}. Open the G app to Approve or Deny."
        task.escalation_question = question
        sms_tool.execute({"to": to, "message": question})

    def resume_task_from_reply(self, task: Task, approved: bool, tool_registry: dict) -> None:
        # update task status according to the replys 
        # we assume a struvrued field that is from the website approve button or llm interpretation of SMS / call resposne
        if not approved:
            task.status = TaskStatus.FAILED
            return
        step = task.task_plan.current_step()
        adapter=tool_registry.get(step.tool)
        if adapter is None:
            raise KeyError(f"No adapter for tool: {step.tool}")
        adapter.execute(step.params)
        step.status= TaskStatus.COMPLETED
        task.task_plan.to_next_step()
        runner = TaskRunner(tool_registry=tool_registry)
        runner.run(task)

    def handle_incoming_message(self, userID: UUID, rawText: str) -> None:
        # call cases
        # TODO: two-way conversation handling
        pass


