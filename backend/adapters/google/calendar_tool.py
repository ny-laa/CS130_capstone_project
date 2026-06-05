# g-cal adapter handles reading + writing cal events
# CalendarTool uses Google OAuth access token to call the g-cal API

from typing import Any
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from adapters.base import BaseToolAdapter
from services.user_service import get_access_token
from uuid import UUID
from sqlalchemy.orm import Session
from config import settings


class CalendarTool(BaseToolAdapter):
    def __init__(self):
        super().__init__("calendar_tool")

    def _build_service(self, access_token: str, refresh_token: str | None = None):
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
        )
        return build("calendar", "v3", credentials=creds)

    def read(
        self,
        access_token: str,
        time_min: str,
        time_max: str,
        calendar_id: str = "primary",
        max_results: int = 10,
        refresh_token: str | None = None,
    ) -> list[dict[str, Any]]:
        service = self._build_service(access_token, refresh_token)
        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        simplified_events = []
        for event in events:
            simplified_events.append(
                {
                    "id": event.get("id"),
                    "summary": event.get("summary", "Untitled event"),
                    "start": event.get("start"),
                    "end": event.get("end"),
                    "location": event.get("location"),
                    "description": event.get("description"),
                }
            )
        return simplified_events

    def check_availability(
        self,
        access_token: str,
        start_time: str,
        end_time: str,
        calendar_id: str = "primary",
        refresh_token: str | None = None,
    ) -> dict[str, Any]:
        service = self._build_service(access_token, refresh_token)

        request_body = {
            "timeMin": start_time,
            "timeMax": end_time,
            "items": [{"id": calendar_id}],
        }

        result = service.freebusy().query(body=request_body).execute()
        busy_windows = (
            result.get("calendars", {})
            .get(calendar_id, {})
            .get("busy", [])
        )

        return {
            "available": len(busy_windows) == 0,
            "busy_windows": busy_windows,
        }

    def write(
        self,
        access_token: str,
        action: str,
        event_body: dict[str, Any] | None = None,
        event_id: str | None = None,
        calendar_id: str = "primary",
        refresh_token: str | None = None,
    ) -> dict[str, Any]:
        service = self._build_service(access_token, refresh_token)

        if action == "create":
            if event_body is None:
                raise ValueError("event_body is required to create an event")
            created_event = (
                service.events()
                .insert(calendarId=calendar_id, body=event_body)
                .execute()
            )
            return {"status": "created", "event": created_event}

        if action == "update" or action == "move":
            if event_id is None:
                raise ValueError("event_id is required to update or move an event")
            if event_body is None:
                raise ValueError("event_body is required to update or move an event")
            updated_event = (
                service.events()
                .patch(calendarId=calendar_id, eventId=event_id, body=event_body)
                .execute()
            )
            return {"status": "updated", "event": updated_event}

        if action == "delete":
            if event_id is None:
                raise ValueError("event_id is required to delete an event")
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            return {"status": "deleted", "event_id": event_id}

        raise ValueError(f"Unsupported calendar action: {action}")

    def execute(self, params: dict[str, Any], db: Session) -> Any:
        user_id: UUID = params.get("user_id")
        if not user_id:
            raise ValueError("user_id needed")

        op = params.get("operation")
        access_token = get_access_token(db, user_id)

        if not access_token:
            raise ValueError("access_token is required")

        if op == "read":
            return self.read(
                access_token=access_token,
                time_min=params["time_min"],
                time_max=params["time_max"],
                calendar_id=params.get("calendar_id", "primary"),
                max_results=params.get("max_results", 10),
            )

        if op == "check_availability":
            return self.check_availability(
                access_token=access_token,
                start_time=params["start_time"],
                end_time=params["end_time"],
                calendar_id=params.get("calendar_id", "primary"),
            )

        if op == "write":
            return self.write(
                access_token=access_token,
                action=params["action"],
                event_body=params.get("event_body"),
                event_id=params.get("event_id"),
                calendar_id=params.get("calendar_id", "primary"),
            )

        raise ValueError(f"Unsupported calendar operation: {op}")