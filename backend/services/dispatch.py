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

from typing import Any

from adapters.communication.call_tool import OutboundCallTool
from adapters.communication.sms_tool import SMSTool
from adapters.google.calendar_tool import CalendarTool
from adapters.google.gmail_tool import GmailTool
from models.user import User


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
def run_plan(plan: dict, user: User) -> list[dict]:
    """Execute each step in `plan["plan_steps"]` through TOOL_REGISTRY.

    For calendar_tool / gmail_tool steps, the user's stored access_token is
    injected into params before execute() — that token never goes through
    the LLM, only through this wrapper.

    Returns a list of `{tool, status, result_or_error}` dicts so the caller
    can surface partial-failure info if needed.
    """
    results: list[dict] = []
    for step in plan.get("plan_steps", []):
        tool_name = step.get("tool")
        params = dict(step.get("params", {}))  # copy, don't mutate caller's dict

        # Inject the right token for google tools
        if tool_name == "calendar_tool" and user.calendar_token:
            params["access_token"] = user.calendar_token
        elif tool_name == "gmail_tool" and user.gmail_token:
            params["access_token"] = user.gmail_token

        adapter = TOOL_REGISTRY.get(tool_name)
        if adapter is None:
            # claude hallucinated a tool name -- log + skip rather than 500
            print(f"[dispatch] unknown tool '{tool_name}', skipping step", flush=True)
            results.append({"tool": tool_name, "status": "skipped", "error": "unknown tool"})
            continue

        try:
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
