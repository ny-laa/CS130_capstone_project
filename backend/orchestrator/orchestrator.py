# this is basically the brain of the whole system
# GOrchestrator: takes a task from the user, builds a plan, dispatches to the right tools
# also handles escalation when G needs human approval before doing smth

from backend.adapters.llm.claude_adapter import ClaudeAdapter
from backend.models.datatypes import TaskType
from uuid import UUID, uuid4
class GOrchestrator:

    def __init__(self, llm_adapter=None):
        # default to claude but you can swap in gpt or anything else thats a BaseLLMAdapter
        self.llm = llm_adapter or ClaudeAdapter()

    def handle(self, query: str, context: dict = None) -> dict:
        # just pass the query straight to the llm adapter
        # context is optional (e.g. calendar events, user prefs)
        return self.llm.handle(query, context)

    def delegate_task(self, message: str, user_id: str, context: dict = None) -> dict:
        # main entry point from the webhook handlers
        # creates a plan and returns it with user_id and PENDING status
        # TODO: actually persist this to the tasks table once db is wired up
        plan = self.llm.handle(message, context)
        return {
            "user_id": user_id,
            "status": "PENDING",
            **plan  # spreads task_type, description, plan_steps, response_message
        }
    

    def handle_incoming_message(self, userID: UUID, rawText: str) -> None:
        # TODO: this is for two-way conversations, where G might ask follow-up questions and the parent can reply
        pass  # will implement this later once we have some basic tasks working

    def resume_task_from_reply(self, userID: UUID, taskID: UUID, replyText: str) -> None:
        # TODO: this is for when G needs to ask the parent a question in the middle of executing a task, e.g. "which event do you want to move?" and then the parent replies with the answer
        pass  # will implement this later once we have some basic tasks working


