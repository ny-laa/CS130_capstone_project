# this is basically the brain of the whole system
# GOrchestrator: takes a task from the user, builds a plan, dispatches to the right tools
# also handles escalation when G needs human approval before doing something

from backend.adapters.llm.claude_adapter import ClaudeAdapter
from backend.models.datatypes import TaskType, TaskStatus
from backend.orchestrator.task_planner import TaskPlanner, Task
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
    

    def handle_incoming_message(self, userID: UUID, rawText: str) -> None:
        # TODO: this is for two-way conversations, where G might ask follow-up questions and the parent can reply
        pass  # will implement this later once we have some basic tasks working

    def resume_task_from_reply(self, userID: UUID, taskID: UUID, replyText: str) -> None:
        # TODO: this is for when G needs to ask the parent a question in the middle of executing a task, e.g. "which event do you want to move?" and then the parent replies with the answer
        pass  # will implement this later once we have some basic tasks working


