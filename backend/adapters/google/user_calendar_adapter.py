# wraps CalendarTool so plan steps only need operation + time params — no access_token.
# fetches the user's token from google_oauth at construction and injects it transparently.
# calls CalendarTool methods directly (bypassing execute's user_id/db path) since the
# token is already resolved from the user object by the time TaskRunner calls this.
# Used gen ai to resolve issues

from typing import Any
from datetime import datetime, timedelta
from adapters.base import BaseToolAdapter
from adapters.google.calendar_tool import CalendarTool
from utils.token_crypto import decrypt_token

_WRITE_ACTIONS = {"create", "update", "delete", "move"}


class UserCalendarAdapter(BaseToolAdapter):
    def __init__(self, user, force_overlap: bool = False, calendar_tool: CalendarTool | None = None):
        super().__init__("calendar_tool")
        oauth = user.google_oauth or {}
        self.token = decrypt_token(oauth.get("access_token"))
        self.refresh_token = decrypt_token(oauth.get("refresh_token"))
        self.force_overlap = force_overlap
        self._tool = calendar_tool or CalendarTool()

    def execute(self, params: dict) -> Any:
        print(f"[UserCalendarAdapter] params: {params}")

        if not self.token:
            raise ValueError("User has no Google Calendar connected — google_oauth is missing")

        # normalize operation
        raw_action = params.get("action")
        operation = params.get("operation")

        if not operation:
            if raw_action in _WRITE_ACTIONS:
                operation = "write"
            elif raw_action == "check_availability":
                operation = "check_availability"
            elif raw_action == "read":
                operation = "read"

        # map query_type values to operations
        if not operation:
            query_type = params.get("query_type")
            if query_type == "availability":
                operation = "check_availability"
            elif query_type in ("events", "read", "lookup"):
                operation = "read"

        # infer from param keys
        if not operation:
            if any(k in params for k in ("event_name", "event_title", "event_body", "summary")):
                operation = "write"
            elif any(k in params for k in ("query_date", "date", "time", "target_time", "datetime")):
                operation = "read"

        if self.force_overlap and operation == "check_availability":
            return {"available": True, "busy_windows": [], "skipped": True}

        if operation == "check_availability":
            start_time = (
                params.get("start_time") or
                params.get("datetime") or
                params.get("target_time") or
                params.get("time")
            )

            if not start_time and "date" in params:
                time_str = params.get("time", "00:00")
                start_time = f"{params['date']}T{time_str}:00-07:00"

            if not start_time:
                raise ValueError("check_availability requires a time parameter")

            end_time = params.get("end_time")
            if not end_time or end_time == start_time:
                try:
                    dt = datetime.fromisoformat(start_time)
                    end_time = (dt + timedelta(hours=1)).isoformat()
                except ValueError:
                    end_time = start_time

            return self._tool.check_availability(
                access_token=self.token,
                refresh_token=self.refresh_token,
                start_time=start_time,
                end_time=end_time,
                calendar_id=params.get("calendar_id", "primary"),
            )

        elif operation == "read":
            time_min = (
                params.get("time_min") or
                params.get("start_time") or
                params.get("date") or
                params.get("query_date")
            )
            time_max = params.get("time_max") or params.get("end_time") or time_min

            return self._tool.read(
                access_token=self.token,
                refresh_token=self.refresh_token,
                time_min=time_min,
                time_max=time_max,
                calendar_id=params.get("calendar_id", "primary"),
                max_results=params.get("max_results", 10),
            )

        elif operation == "write":
            event_body = params.get("event_body")
            if not event_body:
                event_body = {
                    "summary": (
                        params.get("event_name") or
                        params.get("event_title") or
                        params.get("title") or
                        params.get("summary", "New Event")
                    ),
                    "start": {
                        "dateTime": params.get("start_time"),
                        "timeZone": params.get("timezone", "America/Los_Angeles"),
                    },
                    "end": {
                        "dateTime": params.get("end_time"),
                        "timeZone": params.get("timezone", "America/Los_Angeles"),
                    },
                }

            return self._tool.write(
                access_token=self.token,
                refresh_token=self.refresh_token,
                action=raw_action or params.get("write_action", "create"),
                event_body=event_body,
                event_id=params.get("event_id"),
                calendar_id=params.get("calendar_id", "primary"),
            )

        else:
            raise ValueError(f"Unsupported calendar operation: {operation}")