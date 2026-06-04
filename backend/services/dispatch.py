# dispatch claude's plan_steps to the right tool adapter, injecting the user's
# google access_token at runtime for calendar/gmail steps so tokens never go
# through the LLM. mirrors elliot's TaskRunner pattern but stays in our
# import path (her workers/task_runner uses `from backend.X` which breaks
# when uvicorn runs from backend/).
#
# when the project standardizes on running uvicorn from repo root, this can
# be swapped for `TaskRunner(TOOL_REGISTRY).run(task)` directly.

import os
import sys

# radhika's google adapters use `from backend.X` absolute imports. uvicorn
# runs from backend/ so we add the repo root here (this is the only file
# that triggers those imports at app startup time -- main.py doesn't need
# the hack).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from adapters.communication.call_tool import OutboundCallTool
from adapters.communication.sms_tool import SMSTool
from adapters.google.calendar_tool import CalendarTool
from adapters.google.gmail_tool import GmailTool
from models.datatypes import TaskType
from models.user import User
from services.notifications import notify_user
from services.task_service import create_task
from workers.tasks.notifications import notify_user_task


# Tool name string -> adapter instance. Keys match the strings claude puts
# in plan_steps[*].tool. Built once at import.
TOOL_REGISTRY: dict[str, Any] = {
    "sms_tool": SMSTool(),
    "call_tool": OutboundCallTool(),
    "calendar_tool": CalendarTool(),
    "gmail_tool": GmailTool(),
}


# [GenAI Use] Prompt: "write a function that takes claude's raw plan dict
# (with task_type, plan_steps, response_message) and a User row, and runs
# each plan step against the right tool from TOOL_REGISTRY. for calendar_tool
# and gmail_tool steps, inject the user's calendar_token / gmail_token into
# params as `access_token` before calling adapter.execute(). don't mutate
# the caller's plan dict. skip unknown tool names with a warning rather
# than raising -- claude sometimes hallucinates tool names."
# [GenAI Use] LLM Response Start
def run_plan(plan: dict, user: User, db: Session | None = None) -> list[dict]:
    """Execute each step in `plan["plan_steps"]` through TOOL_REGISTRY.

    For calendar_tool / gmail_tool steps, the user's stored access_token is
    injected into params before execute() — that token never goes through
    the LLM, only through this wrapper.

    For sms_tool / call_tool steps that target the registered user, we route
    through notify_user instead of the raw adapter so channel preference and
    outbound logging stay consistent with the proactive notification path
    (morning digest, reminders). force=True because we're inside an active
    conversation -- the user just asked for this, quiet hours don't apply.
    `db` is optional for back-compat with callers that pre-date this routing;
    when None, sms_tool/call_tool fall back to the direct adapter call.

    Returns a list of `{tool, status, result_or_error}` dicts so the caller
    can surface partial-failure info if needed.
    """
    results: list[dict] = []
    for step in plan.get("plan_steps", []):
        tool_name = step.get("tool")
        params = dict(step.get("params", {}))  # copy, don't mutate caller's dict

        # Outbound notification tools -- route through notify_user when we
        # have a db handle so outbound messages get logged + channel routed
        # the same way the scheduler does it.
        if tool_name in ("sms_tool", "call_tool") and db is not None:
            channel = "call" if tool_name == "call_tool" else "sms"
            # claude uses `body` for sms and `message` for calls (matches the
            # adapter execute() shapes), accept either so a hallucinated key
            # doesn't drop the notification on the floor
            message = params.get("body") or params.get("message") or ""
            # `scheduled_at` -> absolute ISO 8601 timestamp. claude is given
            # current_time_iso in context and resolves both "in 2 minutes" and
            # "at 6:55" to an absolute time. omit for immediate.
            scheduled_at_raw = params.get("scheduled_at")
            try:
                if scheduled_at_raw:
                    eta = datetime.fromisoformat(scheduled_at_raw)
                    # past eta: celery will run it immediately, which is the
                    # right move if claude misread the time (better than
                    # rolling forward 24h to the next occurrence and silently
                    # firing tomorrow)
                    if eta < datetime.now(eta.tzinfo):
                        print(
                            f"[dispatch] scheduled_at {scheduled_at_raw} is in the past, firing now",
                            flush=True,
                        )
                    # persist a Task row so the Tasks page can show this
                    # immediately as PENDING. The celery worker drives the
                    # rest of the lifecycle (IN_PROGRESS on entry, COMPLETED
                    # or FAILED on exit) and links the eventual outbound
                    # message row via task_id so it shows in History too.
                    description = (
                        f"Reminder at {eta.strftime('%b %-d, %-I:%M %p')}: "
                        f"{message[:80]}"
                    )
                    task = create_task(
                        db,
                        user_id=user.id,
                        task_type=TaskType.REMINDER,
                        description=description,
                        plan_steps=[step],
                    )
                    notify_user_task.apply_async(
                        args=[str(user.id), message, channel, str(task.id)],
                        eta=eta,
                    )
                    results.append({
                        "tool": tool_name,
                        "status": "scheduled",
                        "scheduled_at": eta.isoformat(),
                        "task_id": str(task.id),
                    })
                else:
                    result = notify_user(
                        db, user, message=message, channel=channel, force=True
                    )
                    results.append({"tool": tool_name, "status": "ok", "result": result})
            except Exception as exc:
                print(f"[dispatch] {tool_name} failed: {type(exc).__name__}: {exc}", flush=True)
                results.append({"tool": tool_name, "status": "error", "error": str(exc)})
            continue

        # Inject the right token for google tools
        # used claude to help me figure out what changes need to be made to this section based on
        # oauth implementation
        if tool_name in ("calendar_tool", "gmail_tool"):
            params["user_id"] = user.id

        adapter = TOOL_REGISTRY.get(tool_name)
        if adapter is None:
            print(f"[dispatch] unknown tool '{tool_name}', skipping step", flush=True)
            results.append({"tool": tool_name, "status": "skipped", "error": "unknown tool"})
            continue

        try:
            if tool_name in ("calendar_tool", "gmail_tool"):
                result = adapter.execute(params, db)
            else:
                result = adapter.execute(params)
            results.append({"tool": tool_name, "status": "ok", "result": result})
        except Exception as exc:
            print(f"[dispatch] {tool_name} failed: {type(exc).__name__}: {exc}", flush=True)
            results.append({"tool": tool_name, "status": "error", "error": str(exc)})

    return results
# [GenAI Use] LLM Response End
# [GenAI Use] Reflection: kept the helper boring on purpose. it's the seam
# elliot's TaskRunner will eventually replace -- same shape (registry +
# per-step execute), just without her StructuredTaskPlan wrapper because
# we'd have to construct a Task() with id/timestamps/escalation_deadline
# that we don't care about in a synchronous webhook. tokens never end up
# in the plan dict claude returned, only in the params we pass to execute --
# checked that with a print + grep.
