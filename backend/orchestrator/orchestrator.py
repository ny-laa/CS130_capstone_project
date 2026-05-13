# this is basically the brain of the whole system
# GOrchestrator: takes a task from the user, builds a plan, dispatches to the right tools
# also handles escalation when G needs human approval before doing something

from backend.adapters.llm.claude_adapter import ClaudeAdapter


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
