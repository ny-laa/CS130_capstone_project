# abstract base class for all tool adapters
# every tool needs to implement execute() so the orchestrator can call them the same way


class BaseToolAdapter:
    def __init__(self, tool_name):
        self.tool_name = tool_name

    def execute(self, params):
        raise NotImplementedError("Each tool adapter must implement the execute method.")
    


