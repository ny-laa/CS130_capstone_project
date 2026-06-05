# wraps CalendarTool so plan steps only need operation + time params — no access_token.
# fetches the user's token from google_oauth at construction and injects it transparently.
# calls CalendarTool methods directly (bypassing execute's user_id/db path) since the
# token is already resolved from the user object by the time TaskRunner calls this.
# Used gen ai to resolve issues

from typing import Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from adapters.base import BaseToolAdapter
from adapters.google.calendar_tool import CalendarTool
from utils.token_crypto import decrypt_token

_WRITE_ACTIONS = {
    "create",
    "update",
    "delete",
    "move",
    "create_event",
    "add_event",
    "schedule_event",
}


class UserCalendarAdapter(BaseToolAdapter):
    def __init__(self, user, force_overlap: bool = False, calendar_tool: CalendarTool | None = None):
        super().__init__("calendar_tool")
        oauth = user.google_oauth or {}
        self.token = decrypt_token(oauth.get("access_token"))
        self.refresh_token = decrypt_token(oauth.get("refresh_token"))
        self.force_overlap = force_overlap
        self._tool = calendar_tool or CalendarTool()

    def _full_day_range(
        self,
        date_str: str,
        timezone_name: str = "America/Los_Angeles",
    ) -> tuple[str, str]:
        tz = ZoneInfo(timezone_name)
        day = datetime.fromisoformat(date_str).date()
        start = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=tz)
        end = start + timedelta(days=1)
        return start.isoformat(), end.isoformat()

    def _with_timezone(
        self,
        datetime_str: str,
        timezone_name: str = "America/Los_Angeles",
    ) -> str:
        dt = datetime.fromisoformat(datetime_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(timezone_name))
        return dt.isoformat()

    def execute(self, params: dict) -> Any:
        print(f"[UserCalendarAdapter] params: {params}")

        if not self.token:
            raise ValueError("User has no Google Calendar connected — google_oauth is missing")

        raw_action = params.get("action")
        operation = params.get("operation")
        query_type = params.get("query_type")

        # Some LLM plans put the action in operation/query_type instead of action.
        if operation in _WRITE_ACTIONS:
            raw_action = operation
            operation = "write"

        if query_type in _WRITE_ACTIONS:
            raw_action = query_type
            operation = "write"

        if not operation:
            if raw_action in _WRITE_ACTIONS:
                operation = "write"
            elif raw_action in ("check_availability", "availability", "get_availability", "free_busy"):
                operation = "check_availability"
            elif raw_action in ("read", "events", "get_events", "list_events", "lookup", "calendar"):
                operation = "read"

        # Map query_type values to operations.
        if not operation:
            if query_type in ("availability", "get_availability", "check_availability", "free_busy"):
                operation = "check_availability"
            elif query_type in ("events", "get_events", "list_events", "read", "lookup", "calendar"):
                operation = "read"

        # Infer from param keys.
        if not operation:
            has_title = any(
                k in params
                for k in ("event_name", "event_title", "event_body", "summary", "title")
            )
            has_event_times = any(k in params for k in ("start_time", "end_time", "start", "end"))

            if has_title or has_event_times:
                operation = "write"
            elif any(k in params for k in ("time", "target_time", "datetime", "query_time")):
                operation = "check_availability"
            elif any(k in params for k in ("query_date", "date", "time_min")):
                operation = "read"

        if self.force_overlap and operation == "check_availability":
            return {"available": True, "busy_windows": [], "skipped": True}

        if operation == "check_availability":
            timezone_name = params.get("timezone", "America/Los_Angeles")

            if "date" in params and "time" in params:
                time_str = params.get("time", "00:00")
                start_time = self._with_timezone(
                    f"{params['date']}T{time_str}:00",
                    timezone_name,
                )
            else:
                start_time = (
                    params.get("start_time")
                    or params.get("datetime")
                    or params.get("target_time")
                    or params.get("time")
                )

                if start_time:
                    start_time = self._with_timezone(start_time, timezone_name)

            if not start_time and "date" in params:
                start_time, end_time = self._full_day_range(params["date"], timezone_name)
            else:
                end_time = params.get("end_time")

            if not start_time:
                raise ValueError("check_availability requires a time parameter")

            if end_time:
                end_time = self._with_timezone(end_time, timezone_name)

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
            timezone_name = params.get("timezone", "America/Los_Angeles")
            date_only = params.get("date") or params.get("query_date")

            if date_only and "T" not in date_only:
                time_min, time_max = self._full_day_range(date_only, timezone_name)
            else:
                time_min = (
                    params.get("time_min")
                    or params.get("start_time")
                    or date_only
                )
                time_max = params.get("time_max") or params.get("end_time")

                if time_min:
                    time_min = self._with_timezone(time_min, timezone_name)

                if time_max:
                    time_max = self._with_timezone(time_max, timezone_name)

                # If only one timestamp is provided for a read, default to a 1-day window.
                if time_min and not time_max:
                    try:
                        dt = datetime.fromisoformat(time_min)
                        time_max = (dt + timedelta(days=1)).isoformat()
                    except ValueError:
                        time_max = time_min

            if not time_min or not time_max:
                raise ValueError("read requires date, query_date, time_min, or start_time")

            return self._tool.read(
                access_token=self.token,
                refresh_token=self.refresh_token,
                time_min=time_min,
                time_max=time_max,
                calendar_id=params.get("calendar_id", "primary"),
                max_results=params.get("max_results", 10),
            )

        elif operation == "write":
            timezone_name = params.get("timezone", "America/Los_Angeles")

            event_body = params.get("event_body")
            if not event_body:
                start_time = (
                    params.get("start_time")
                    or params.get("scheduled_at")
                    or params.get("start")
                    or params.get("datetime")
                    or params.get("time")
                )
                end_time = params.get("end_time") or params.get("end")

                if start_time:
                    start_time = self._with_timezone(start_time, timezone_name)

                if end_time:
                    end_time = self._with_timezone(end_time, timezone_name)
                elif start_time:
                    try:
                        dt = datetime.fromisoformat(start_time)
                        end_time = (dt + timedelta(hours=1)).isoformat()
                    except ValueError:
                        end_time = start_time

                event_body = {
                    "summary": (
                        params.get("event_name")
                        or params.get("event_title")
                        or params.get("title")
                        or params.get("summary")
                        or "New Event"
                    ),
                    "start": {
                        "dateTime": start_time,
                        "timeZone": timezone_name,
                    },
                    "end": {
                        "dateTime": end_time,
                        "timeZone": timezone_name,
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