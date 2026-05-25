# twilio sms adapter - sends outbound texts to the parent
# SMSTool, implements execute() from base

import os

from twilio.rest import Client

from adapters.base import BaseToolAdapter


# [GenAI Use] Prompt: "Implement a Twilio outbound SMS adapter in Python. It must
# (1) inherit from BaseToolAdapter in backend/adapters/base.py, (2) expose
# send(to, body) -> str that returns Twilio's message SID, (3) expose
# execute(params: dict) -> dict so the orchestrator can call it uniformly with
# other tools, and (4) read TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_FROM_NUMBER
# from env vars as a fallback when args aren't passed to __init__. Use the
# official twilio Python SDK."
# [GenAI Use] LLM Response Start
class SMSTool(BaseToolAdapter):
    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_number: str | None = None,
    ):
        super().__init__(tool_name="sms")
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = from_number or os.getenv("TWILIO_FROM_NUMBER")
        self.client = Client(self.account_sid, self.auth_token)

    def send(self, to: str, body: str) -> str:
        """Send an SMS. Returns Twilio's message SID."""
        message = self.client.messages.create(
            from_=self.from_number,
            to=to,
            body=body,
        )
        return message.sid

    def execute(self, params: dict) -> dict:
        """BaseToolAdapter contract — orchestrator calls all tools uniformly via execute()."""
        sid = self.send(to=params["to"], body=params["body"])
        return {"status": "sent", "sid": sid}
# [GenAI Use] LLM Response End
# [GenAI Use] Reflection: I reviewed the generated class and confirmed it matches
# our BaseToolAdapter contract. The env-var fallback pattern mirrors how
# ClaudeAdapter handles its own credentials, which keeps things consistent.
