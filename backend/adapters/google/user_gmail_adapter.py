# wraps GmailTool so TaskRunner can call it without a db session.
# mirrors UserCalendarAdapter — fetches user's token at construction, injects transparently.

from typing import Any
from adapters.base import BaseToolAdapter
from adapters.google.gmail_tool import GmailTool

# [GenAI Use] Prompt: write a UserGmailAdapter just like UserCalendarAdapter but for gmail. user token comes from user.google_oauth at init, then execute() just calls GmailTool.read() with it. injectable gmail_tool for testing
# [GenAI Use] LLM Response Start
class UserGmailAdapter(BaseToolAdapter):
    def __init__(self, user, gmail_tool: GmailTool | None = None):
        super().__init__("gmail_tool")
        self.token = (user.google_oauth or {}).get("access_token")
        self._tool = gmail_tool or GmailTool()

    def execute(self, params: dict) -> Any:
        if not self.token:
            raise ValueError("User has no Gmail connected — google_oauth is missing")

        return self._tool.read(
            access_token=self.token,
            query=params.get("query", ""),
            max_results=params.get("max_results", 10),
            include_body=params.get("include_body", False),
        )
# [GenAI Use] LLM Response End
# [GenAI Use] Reflection: clean copy of the calendar adapter pattern, same token injection idea, works the same way with TaskRunner
