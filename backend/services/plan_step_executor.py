# Single source of truth for "run one plan step against the right
# user-bound adapter". Used by:
#   - workers.tasks.plan_step.run_plan_step_task (Celery eta path)
#   - services.scheduled_task_scanner (in-process safety net)
#
# Keeping this in one place means scheduled steps fire identically
# whether celery picks them up at the eta or the scanner sweeps them
# up later. Add a new scheduled-capable tool by adding one branch.

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from adapters.communication.business_call_tool import UserBusinessCallAdapter
from adapters.communication.user_call_adapter import UserCallAdapter
from adapters.communication.user_sms_adapter import UserSMSAdapter
from models.user import User

logger = logging.getLogger("backend.services.plan_step_executor")


def execute_step(db: Session, user: User, step: dict[str, Any]) -> dict[str, Any]:
    """Execute a single plan_step on behalf of `user`. Returns a dict
    shaped like {"status": "ok"|"error", ...}.

    scheduled_at is stripped before execute() — by the time we're here,
    the eta has already passed (celery beat us to it, or the scanner
    fired). Leaving scheduled_at in params would just be noise for the
    adapters.
    """
    tool = step.get("tool")
    params = dict(step.get("params") or {})
    params.pop("scheduled_at", None)

    if tool == "sms_tool":
        adapter = UserSMSAdapter(user)
        result = adapter.execute(params)
        return {"status": "ok", "result": result}

    if tool == "call_tool":
        adapter = UserCallAdapter(user)
        result = adapter.execute(params)
        return {"status": "ok", "result": result}

    if tool == "business_call_tool":
        adapter = UserBusinessCallAdapter(user)
        result = adapter.execute(params)
        return {"status": "ok", "result": result}

    # google tools (calendar / gmail) take a db handle and execute
    # differently -- intentionally not handled here yet. add when needed.
    logger.warning("execute_step: tool=%r not schedulable here", tool)
    return {"status": "error", "error": f"unsupported scheduled tool: {tool}"}
