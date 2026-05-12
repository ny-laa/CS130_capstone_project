# claude is our main llm (anthropic api)
# primary adapter, most requests go thru here
# wraps the anthropic sdk and gives back a structured dict that the orchestrator can use to build a task plan

import anthropic
import json
import os

from .base_llm_adapter import BaseLLMAdapter


# system prompt that tells claude who it is and what format to respond in
# keep this in sync with the task schema in models/task.py
SYSTEM_PROMPT = """You are G, an AI personal secretary that helps parents manage their day.
When given a request, figure out what the parent needs and respond with a JSON object only — no extra text.

Use this exact format:
{
    "task_type": "<one of: reminder, calendar_update, information_request, morning_digest>",
    "description": "<short summary of what the parent is asking for>",
    "plan_steps": [
        {"tool": "<tool name>", "params": {}, "status": "PENDING"}
    ],
    "response_message": "<friendly confirmation to send back to the parent via sms>"
}

Tools you can use: sms_tool, calendar_tool, gmail_tool, call_tool
Only respond with the JSON, nothing else."""


class ClaudeAdapter(BaseLLMAdapter):

    def __init__(self, api_key=None, model="claude-opus-4-7"):
        # grab api key from env if not passed in directly
        self.client = anthropic.Anthropic(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY")
        )
        self.model = model

    def handle(self, query: str, context: dict = None) -> dict:
        # build the user message, optionally prepend context (like calendar data)
        user_message = query
        if context:
            # stick the context at the top so claude sees it before the question
            context_str = json.dumps(context, default=str, indent=2)
            user_message = f"Here is some context:\n{context_str}\n\nRequest: {query}"

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )

        # pull the text out of the response
        raw = response.content[0].text.strip()

        # sometimes claude wraps the json in markdown code fences, strip those
        if raw.startswith("```"):
            lines = raw.splitlines()
            # drop first line (```json or ```) and last line (```)
            raw = "\n".join(lines[1:-1])

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # fallback if claude doesnt return valid json for some reason
            # shouldnt happen often but just in case
            return {
                "task_type": "information_request",
                "description": raw,
                "plan_steps": [],
                "response_message": raw
            }
