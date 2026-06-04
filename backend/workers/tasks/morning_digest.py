# celery task + helpers for sending ussers daily morning calendar digest
# celery beat will call send_morning_digests_task automatically each morning
# for now, all demo users use the America/Los_Angeles timezone
# we send a nice message even if there is no gcal events :) 

# used: https://developers.google.com/workspace/calendar/api/guides/overview documentation to guide code implementation


from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo
from adapters.google.calendar_tool import CalendarTool
from database import session_scope
from models.user import User
from services.notifications import notify_user
from workers.celery_app import app


DEFAULT_TIMEZONE = "America/Los_Angeles" # global prototype timezone is LA


def _as_rfc3339(value: datetime) -> str:
    # gcal expects RFC3339 datetime strings
    # use Z instead of +00:00 to keep the UTC timestamps easier to read
    return value.isoformat().replace("+00:00", "Z")


def _today_time_window(
    now: datetime | None = None,
    timezone_name: str = DEFAULT_TIMEZONE,
) -> tuple[str, str]:
    # hanldes returing start + end of current day as UTC RFC3339 strings

    # at the very least, digest has evenyts of today in local time zone, for now all demo users are in LA
  
    local_timezone = ZoneInfo(timezone_name)

    if now is None:
        local_now = datetime.now(local_timezone)
    elif now.tzinfo is None:
        local_now = now.replace(tzinfo=local_timezone)
    else:
        local_now = now.astimezone(local_timezone)

    start_local = local_now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    end_local = start_local + timedelta(days=1)

    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    return _as_rfc3339(start_utc), _as_rfc3339(end_utc)


def _format_event_time(
    event: dict[str, Any],
    timezone_name: str = DEFAULT_TIMEZONE,
) -> str:
    # Google uses "date" for all-day events +  "dateTime" for timed events
    start = event.get("start") or {}

    if start.get("date"):
        return "All day"

    date_time = start.get("dateTime")
    if not date_time:
        return "Time not listed"

    # Handle the case is Google returns UTC timestamps ending in Z
    parsed_time = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
    local_time = parsed_time.astimezone(ZoneInfo(timezone_name))

    return local_time.strftime("%I:%M %p").lstrip("0")


def format_morning_digest(
    events: list[dict[str, Any]],
    timezone_name: str = DEFAULT_TIMEZONE,
) -> str:
    # take gcal eventt => mornging message :) 

    if not events:
        return "Good morning! You do not have any calendar events today. Feel free to add some or rest up :)"

    lines = ["Good morning! Here is your schedule for today:"]

    for event in events:
        summary = event.get("summary") or "Untitled event"
        event_time = _format_event_time(event, timezone_name)
        location = event.get("location")

        line = f"- {event_time}: {summary}"
        if location:
            line += f" at {location}"

        lines.append(line)

    return "\n".join(lines)


def send_morning_digest_for_user(
    db,
    user: User,
    calendar_tool: CalendarTool | None = None,
    now: datetime | None = None,
    timezone_name: str = DEFAULT_TIMEZONE,
) -> dict:
    # gets the cal events from today + sends over to user 
    
    # note that notify_user handles preferred channel, quiet hours, Twilio sending, and outbound message logging already 

    access_token = (user.google_oauth or {}).get("access_token")
    if not access_token:
        return {
            "status": "skipped_missing_calendar_token",
            "event_count": 0,
        }

    tool = calendar_tool or CalendarTool()
    time_min, time_max = _today_time_window(
        now=now,
        timezone_name=timezone_name,
    )

    events = tool.read(
        access_token=access_token,
        time_min=time_min,
        time_max=time_max,
        max_results=50,
    )

    message = format_morning_digest(
        events=events,
        timezone_name=timezone_name,
    )

    result = notify_user(
        db=db,
        user=user,
        message=message,
        force=True,
    )

    result["event_count"] = len(events)
    return result


@app.task(name="send_morning_digests")
def send_morning_digests_task() -> dict:
    # this is diff from the function above cause it handles scheduled Celery job that finds all eligible parents and calls the first function for each one
    
    # in the future, we can expand the prefs section to include more filters for things like timezone + whether a user wants the digest turned on at all 
  
    results = []

    with session_scope() as db: #open up a new db sesh 
        users = (
            db.query(User)
            .filter(User.google_oauth.isnot(None))
            .all()
        )

        for user in users:
            try:
                result = send_morning_digest_for_user(
                    db=db,
                    user=user,
                )
            except Exception as exc:
                result = {
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }

            results.append(
                {
                    "user_id": str(user.id),
                    **result,
                }
            )

    return {
        "status": "completed",
        "processed_users": len(results),
        "results": results,
    }