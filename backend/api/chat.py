# POST /api/chat — web UI chat endpoint.
# Routes messages through the same LLM adapter the SMS webhook uses so the
# frontend gets real Claude responses without needing a browser-side API key.

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from adapters.llm.claude_adapter import ClaudeAdapter
from database import get_db
from services.user_context_service import build_user_context
from services.user_service import get_user_by_id

router = APIRouter()

_llm = ClaudeAdapter(model="claude-haiku-4-5-20251001")

# [GenAI Use] Prompt: "I'm building G.ai, a FastAPI backend for a parent's AI secretary. The SMS webhook already handles messages by calling _llm.handle(body, SMS_SYSTEM_PROMPT, context=user_context) and getting back a plan dict with response_message and optional plan_steps. I need a POST /api/chat endpoint for the React frontend chat page that does the same LLM call — same system prompt shape, same context build — but over HTTP instead of Twilio. No Twilio validation needed. Accept { message, user_id? }. If user_id is given, build user context the same way sms.py does. Return { reply } where reply is response_message from the plan, with a <task> XML block appended when the plan has a task_type and description so the existing frontend parseTaskBlock() function keeps working unchanged."
# [GenAI Use] LLM Response Start
_CHAT_SYSTEM_PROMPT = """You are G, an AI personal secretary helping a parent over chat.
Keep your response_message short and conversational — no markdown.

Respond with a JSON object only, no extra text:
{
    "task_type": "<one of: reminder, calendar_update, information_request, morning_digest, smalltalk>",
    "description": "<short summary of what the parent is asking for>",
    "plan_steps": [
        {"tool": "<tool name>", "params": {}, "status": "PENDING"}
    ],
    "response_message": "<friendly reply to send back to the parent>"
}

Tools you can use: sms_tool, calendar_tool, gmail_tool, call_tool"""

_TASK_TYPE_LABEL = {
    "reminder": "Reminder",
    "calendar_update": "Calendar",
    "information_request": "Escalation",
    "morning_digest": "Reminder",
}


class ChatRequest(BaseModel):
    message: str
    user_id: str | None = None


@router.post("/api/chat")
def chat(body: ChatRequest):
    context = {"current_time_iso": datetime.now().astimezone().isoformat()}

    if body.user_id:
        try:
            from database import SessionLocal
            db = SessionLocal()
            user = get_user_by_id(db, UUID(body.user_id))
            if user:
                context.update(build_user_context(db, user.id))
            db.close()
        except Exception:
            pass

    try:
        plan = _llm.handle(body.message, _CHAT_SYSTEM_PROMPT, context=context)
    except Exception:
        return {"reply": "Sorry, I had trouble with that. Try again?"}

    reply = (plan.get("response_message") or "").strip() or "Got it."

    task_type = plan.get("task_type")
    description = plan.get("description")
    if task_type and description and task_type != "smalltalk":
        label = _TASK_TYPE_LABEL.get(task_type, "Reminder")
        reply = (
            f"{reply}\n<task>"
            f"<type>{label}</type>"
            f"<status>Pending</status>"
            f"<description>{description}</description>"
            f"<summary>{description[:80]}</summary>"
            f"</task>"
        )

    return {"reply": reply}
# [GenAI Use] LLM Response End
# [GenAI Use] Reflection: The structure matched what I needed. I kept the same SMS system prompt shape (JSON plan with response_message) so the LLM path stays consistent across channels. Added the <task> XML transformation so parseTaskBlock() in api.js keeps working without any frontend changes. Wrapped the user context lookup in a try/except so a bad or missing user_id doesn't crash the endpoint — the chat still works unauthenticated for the demo.
