# wraps OutboundCallTool so plan steps only need `message` -- the `to`
# is bound to the user's phone number at construction. claude doesn't
# get the user's number, this layer fills it.

from typing import Any

from adapters.base import BaseToolAdapter
from adapters.communication.call_tool import OutboundCallTool


class UserCallAdapter(BaseToolAdapter):
    def __init__(self, user, call_tool: OutboundCallTool | None = None):
        super().__init__("call_tool")
        self.to = user.phone_number
        self._tool = call_tool or OutboundCallTool()

    def execute(self, params: dict) -> Any:
        if not self.to:
            raise ValueError(
                "User has no phone_number set -- finish onboarding before "
                "G can call this account."
            )

        # claude usually fills `message`, but sometimes uses `body` for
        # cross-tool consistency. accept either.
        message = params.get("message") or params.get("body")
        if not message:
            raise ValueError("call step missing `message` (or `body`) param")

        return self._tool.execute({"to": self.to, "message": message})
