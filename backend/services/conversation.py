# shared "user sent a message" handler. processes one inbound message
# (whatever the channel) end-to-end: log it, run claude with full user
# context, dispatch any plan_steps claude returned, log the reply, and
# return the reply text + any task ids that got created.
#
# both /webhooks/sms (real twilio sms) and /api/users/{id}/chat (browser
# chat) call this. all stored messages use channel="sms" so the browser
# chat is indistinguishable from a real text in the audit log -- that's
# intentional, matches the product framing of "chat is just sms over the
# web". the history page and tasks page both fetch from the canonical
# DB rows so the same conversation surfaces everywhere.

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from adapters.llm.claude_adapter import ClaudeAdapter
from models.user import User
from services import dispatch
from services.message_service import log_message
from services.user_context_service import build_user_context


# Shared with /webhooks/sms.py -- defined here so both call sites stay
# in sync. If chat and SMS need to diverge (e.g. chat can use longer
# replies and markdown), split into two prompts and pass the right one
# in at call time.
SYSTEM_PROMPT = """You are G, an AI personal secretary helping a parent over SMS.
Your response_message will be sent back as a text message, so keep it short (under 160 characters when possible) and avoid markdown or emoji.

Respond with a JSON object only, no extra text:
{
    "task_type": "<one of: reminder, calendar_update, information_request, morning_digest, smalltalk>",
    "description": "<short summary of what the parent is asking for>",
    "plan_steps": [
        {"tool": "<tool name>", "params": {}, "status": "PENDING"}
    ],
    "response_message": "<short reply, will be sent as SMS>"
}

Tools you can use: sms_tool, calendar_tool, gmail_tool, call_tool

The current time is provided in the context as `current_time_iso` (ISO 8601 with timezone offset). For sms_tool / call_tool, when the parent asks you to reach out *later* -- either an absolute time ("at 5pm", "tomorrow at 8am") OR a relative duration ("in 30 minutes", "in 2 hours") -- set `params.scheduled_at` to the absolute ISO 8601 timestamp (same timezone as `current_time_iso`) when the notification should fire. Examples: if current_time_iso is "2026-05-31T18:48:00-07:00" and the parent says "in 2 minutes", scheduled_at is "2026-05-31T18:50:00-07:00". If they say "at 6:55", it's "2026-05-31T18:55:00-07:00". Omit `scheduled_at` when the parent wants the action immediately."""


# module-level llm singleton -- reuse the HTTP connection pool across
# requests. same pattern as the webhooks file.
_llm = ClaudeAdapter()


def handle_user_message(db: Session, user: User, body: str) -> dict[str, Any]:
    """Process one inbound user message end-to-end.

    Side effects, in order:
      1. log inbound row to DB (channel="sms", direction="inbound")
      2. call claude with build_user_context() + current_time_iso
      3. dispatch any plan_steps claude returned (may persist Task rows
         for scheduled outbound; may fire google tools immediately, etc.)
      4. log outbound row to DB (channel="sms", direction="outbound")
         regardless of whether the caller actually delivers the reply
         via Twilio -- mirrors the A2P-pending behavior on /webhooks/sms.

    Returns { "reply": str, "tasks_created": [task_id_str, ...] }.

    The caller decides what to do with the reply: webhooks/sms.py fires
    SMSTool.send(), api/chat.py returns it as JSON. We don't deliver the
    reply here because the delivery mechanism is channel-specific.
    """
    # 1. log inbound. wrap in try -- a logging failure shouldn't block
    # the reply path. an inbound row that fails to log means History
    # has a gap, but the reply still went out, which is the right
    # tradeoff for a webhook context.
    try:
        log_message(
            db, content=body, direction="inbound", channel="sms", user_id=user.id
        )
    except Exception as exc:
        print(f"[conversation log_inbound] {type(exc).__name__}: {exc}", flush=True)

    # 2. claude with full user context. dispatch errors below shouldn't
    # erase a good reply, so we compute reply first then dispatch.
    try:
        user_context = build_user_context(db, user.id)
        user_context["current_time_iso"] = datetime.now().astimezone().isoformat()
        plan = _llm.handle(body, SYSTEM_PROMPT, context=user_context)
        reply = (plan.get("response_message") or "").strip() or "Got it."
    except Exception as exc:
        print(f"[conversation llm] {type(exc).__name__}: {exc}", flush=True)
        plan = {}
        reply = "Sorry, I had trouble with that. Try again?"

    # 3. dispatch plan_steps. tokens get injected from `user` inside
    # dispatch (never via the LLM). dispatch errors are caught so a
    # broken plan_step (e.g. malformed calendar params) doesn't 500
    # the caller -- Twilio retries on 5xx; the frontend doesn't need
    # to either.
    tasks_created: list[str] = []
    if plan.get("plan_steps"):
        try:
            results = dispatch.run_plan(plan, user, db)
            for r in results or []:
                if r.get("task_id"):
                    tasks_created.append(str(r["task_id"]))
        except Exception as exc:
            print(f"[conversation dispatch] {type(exc).__name__}: {exc}", flush=True)

    # 4. log outbound. logged regardless of whether the caller actually
    # delivers -- a2p-pending sends still need to show in History, and
    # chat doesn't have a "delivery" step at all (the frontend just
    # renders the reply we return).
    try:
        log_message(
            db, content=reply, direction="outbound", channel="sms", user_id=user.id
        )
    except Exception as exc:
        print(f"[conversation log_outbound] {type(exc).__name__}: {exc}", flush=True)

    return {"reply": reply, "tasks_created": tasks_created}
