# wraps CalendarTool so plan steps only need operation + time params — no access_token.
# fetches the user's calendar_token once at construction and injects it transparently.
# used in the tool_registry passed to TaskRunner so the LLM never sees credentials.
# used to check for avaliability from the actual google calendar. 

from typing import Any
from adapters.base import BaseToolAdapter
from adapters.google.calendar_tool import CalendarTool


class UserCalendarAdapter(BaseToolAdapter):
    def __init__(self, user, force_overlap: bool = False, calendar_tool: CalendarTool | None = None):
        super().__init__("calendar_tool")
        self.token = user.calendar_token
        self.force_overlap = force_overlap  # True when parent approved adding despite a conflict
        self._tool = calendar_tool or CalendarTool()

    def execute(self, params: dict) -> Any:
        if not self.token:
            raise ValueError(f"User has no Google Calendar connected — calendar_token is missing")

        enriched = {**params, "access_token": self.token}

        # if the parent approved overlapping, skip the availability check step entirely
        if self.force_overlap and enriched.get("operation") == "check_availability":
            return {"available": True, "busy_windows": [], "skipped": True}

        return self._tool.execute(enriched)
