# G calls an external business on behalf of the parent and drives a
# goal-oriented conversation with whoever answers (e.g. "order one large
# pepperoni delivered to 123 Main St"). distinct from UserCallAdapter,
# which dials the *user* with a one-way message.
#
# split of responsibility:
#   - this adapter: builds the opening line, places the outbound call via
#     OutboundCallTool, registers per-call state keyed by twilio CallSid.
#   - /webhooks/call/outbound-transcript: handles each subsequent turn by
#     reading the state, asking claude what to say next, hanging up when
#     the goal's done, SMSing the user a summary on exit.
#
# why user-scoped (constructed with `user`): the opening line needs the
# parent's name ("calling on behalf of <name>") and the eventual summary
# SMS needs the parent's phone -- claude is never given either.

import datetime as _dt
import os
from typing import Any
from uuid import UUID

from adapters.base import BaseToolAdapter
from adapters.communication.call_tool import OutboundCallTool
from services import outbound_call_state


class UserBusinessCallAdapter(BaseToolAdapter):
    def __init__(
        self,
        user,
        call_tool: OutboundCallTool | None = None,
    ):
        super().__init__("business_call_tool")
        self.user_id: UUID = user.id
        self.user_name: str = (user.full_name or "the user").strip()
        self.user_phone: str | None = user.phone_number
        self._tool = call_tool or OutboundCallTool()

    def execute(self, params: dict) -> Any:
        to = params.get("to")
        goal = (params.get("goal") or params.get("message") or "").strip()
        business_name = params.get("business_name")

        if not to:
            raise ValueError("business_call_tool requires `to` (the business phone number)")
        if not goal:
            raise ValueError("business_call_tool requires `goal` (what to accomplish on the call)")

        # twilio needs an absolute URL to POST the employee's speech to.
        # priority:
        #   1. PUBLIC_BASE_URL  -- local dev override (ngrok url)
        #   2. RAILWAY_PUBLIC_DOMAIN -- auto-injected on railway, no setup
        #   3. hardcoded prod URL -- last-resort fallback so demos don't break
        # nothing for the user to configure when deploying on railway.
        railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
        public_base = (
            os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
            or (f"https://{railway_domain}" if railway_domain else "")
            or "https://cs130capstoneproject-production.up.railway.app"
        )
        callback_url = f"{public_base}/webhooks/call/outbound-transcript"

        # opening line. disclose the AI up front -- (a) it's the honest
        # thing to do, (b) reduces the chance the employee hangs up
        # thinking it's a spam robocall.
        # keep the opening short. don't dump the whole goal in turn 1 --
        # if we do, claude tends to read the employee's "ok sure" as
        # "goal achieved" and hangs up after one round-trip. let claude
        # share details across multiple turns instead.
        opening = (
            f"Hi, this is G, an AI assistant calling on behalf of "
            f"{self.user_name}. Do you have a moment? I'm calling to "
            f"take care of something on their behalf."
        )

        sid = self._tool.place_call(
            to=to,
            message=opening,
            callback_url=callback_url,
        )

        # store the call state so the webhook can pick up where we left off.
        # opening line goes into history as the assistant's first turn so
        # claude has the full conversation in front of it from turn 2 on.
        outbound_call_state.register(
            sid,
            outbound_call_state.OutboundCallState(
                user_id=self.user_id,
                user_phone=self.user_phone or "",
                user_name=self.user_name,
                goal=goal,
                business_name=business_name,
                history=[{"role": "assistant", "content": opening}],
                started_iso=_dt.datetime.now().astimezone().isoformat(),
            ),
        )

        return {"status": "calling", "sid": sid, "to": to, "goal": goal}
