# twilio outbound call adapter - G calls businesses on behalf of the parent
# OutboundCallTool, implements execute() from base

import os
from xml.sax.saxutils import escape

from twilio.rest import Client

from adapters.base import BaseToolAdapter


# [GenAI Use] Prompt: "Implement a Twilio outbound voice-call adapter in Python,
# mirroring the SMSTool I just built. Constraints: (1) inherit from
# BaseToolAdapter; (2) expose place_call(to, message) -> str that dials the
# given number and reads the message aloud via Twilio's TTS, returning the
# call SID; (3) expose execute(params: dict) -> dict for orchestrator uniformity;
# (4) read TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_PHONE_NUMBER from env vars
# as fallback. Use the inline-TwiML pattern (twiml=... on calls.create) so no
# webhook is needed for the outbound side. Escape the message before
# interpolating it into the TwiML so user/LLM content doesn't break the XML."
# [GenAI Use] LLM Response Start
class OutboundCallTool(BaseToolAdapter):
    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_number: str | None = None,
    ):
        super().__init__(tool_name="call")
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = from_number or os.getenv("TWILIO_PHONE_NUMBER")
        self.client = Client(self.account_sid, self.auth_token)

    def place_call(self, to: str, message: str, callback_url: str | None = None) -> str:
        """Dial `to` and read `message` aloud via Twilio's TTS. Returns the call SID.

        If `callback_url` is given, Twilio gathers the recipient's speech after
        the message and POSTs the transcript to that URL — so the call becomes
        a back-and-forth. Without it the call hangs up after the message
        (fire-and-forget reminder).

        Uses inline TwiML — no inbound webhook needed for the read-aloud-only
        path. Same pattern callendar uses.
        """
        if callback_url:
            twiml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<Response>"
                f"<Say>{escape(message)}</Say>"
                f'<Gather input="speech" action="{escape(callback_url)}"'
                ' method="POST" speechTimeout="auto" />'
                "<Say>Goodbye.</Say>"
                "</Response>"
            )
        else:
            twiml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f"<Response><Say>{escape(message)}</Say></Response>"
            )
        call = self.client.calls.create(
            twiml=twiml,
            to=to,
            from_=self.from_number,
        )
        return call.sid

    def execute(self, params: dict) -> dict:
        """BaseToolAdapter contract — orchestrator calls all tools uniformly via execute()."""
        sid = self.place_call(
            to=params["to"],
            message=params["message"],
            callback_url=params.get("callback_url"),
        )
        return {"status": "called", "sid": sid}
# [GenAI Use] LLM Response End
# [GenAI Use] Reflection: basically SMSTool but for calls. the thing i had to
# look up was whether twilio can read a message out loud without a webhook on
# my end. turns out you can pass twiml='...' directly to calls.create() and
# they execute it server-side, so no ngrok needed for outbound calls. Looks nice
