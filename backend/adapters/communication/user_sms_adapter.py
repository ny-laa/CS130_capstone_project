# wraps SMSTool so plan steps only need `body` -- the `to` field is bound
# to the user's phone number at construction, since claude isn't expected
# to know the user's number. mirrors the pattern in
# adapters.google.user_calendar_adapter (and user_gmail_adapter) where the
# auth-y bits are resolved from the user object before the LLM ever sees
# them.

from typing import Any

from adapters.base import BaseToolAdapter
from adapters.communication.sms_tool import SMSTool


class UserSMSAdapter(BaseToolAdapter):
    def __init__(self, user, sms_tool: SMSTool | None = None):
        super().__init__("sms_tool")
        # bind the phone at construction. if the user finished onboarding
        # this is set; otherwise execute() will raise.
        self.to = user.phone_number
        self._tool = sms_tool or SMSTool()

    def execute(self, params: dict) -> Any:
        if not self.to:
            raise ValueError(
                "User has no phone_number set -- finish onboarding before "
                "sending an SMS to this account."
            )

        # claude usually fills `body`, but sometimes uses `message` for
        # cross-tool consistency with call_tool. accept either so a tiny
        # naming hallucination doesn't 500 the task.
        body = params.get("body") or params.get("message")
        if not body:
            raise ValueError("SMS step missing `body` (or `message`) param")

        return self._tool.execute({"to": self.to, "body": body})
