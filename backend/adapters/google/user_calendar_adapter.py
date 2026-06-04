# wraps CalendarTool so plan steps only need operation + time params — no access_token.
# fetches the user's token from google_oauth at construction and injects it transparently.
# calls CalendarTool methods directly (bypassing execute's user_id/db path) since the
# token is already resolved from the user object by the time TaskRunner calls this.

from typing import Any
from adapters.base import BaseToolAdapter
from adapters.google.calendar_tool import CalendarTool


class UserCalendarAdapter(BaseToolAdapter):
    def __init__(self, user, force_overlap: bool = False, calendar_tool: CalendarTool | None = None):
        super().__init__("calendar_tool")
        self.token = (user.google_oauth or {}).get("access_token")
        self.force_overlap = force_overlap  # True when parent approved adding despite a conflict
        self._tool = calendar_tool or CalendarTool()

    def execute(self, params: dict) -> Any:
        if not self.token:
            raise ValueError("User has no Google Calendar connected — google_oauth is missing")

        operation = params.get("operation")

        if self.force_overlap and operation == "check_availability":
            return {"available": True, "busy_windows": [], "skipped": True}

        if operation == "check_availability":
            return self._tool.check_availability(
                access_token=self.token,
                start_time=params["start_time"],
                end_time=params["end_time"],
                calendar_id=params.get("calendar_id", "primary"),
            )
        elif operation == "read":
            return self._tool.read(
                access_token=self.token,
                time_min=params["time_min"],
                time_max=params["time_max"],
                calendar_id=params.get("calendar_id", "primary"),
                max_results=params.get("max_results", 10),
            )
        elif operation == "write":
            return self._tool.write(
                access_token=self.token,
                action=params["action"],
                event_body=params.get("event_body"),
                event_id=params.get("event_id"),
                calendar_id=params.get("calendar_id", "primary"),
            )
        else:
            raise ValueError(f"Unsupported calendar operation: {operation}")
