# basic tests for dispatch helper. used claude to brainstorm edge cases
# and wrote most of these myself off its list. the two below have full
# [GenAI Use] blocks when i borrowed speficically 

from unittest.mock import MagicMock, patch
from uuid import uuid4

from services.dispatch import TOOL_REGISTRY, run_plan


def _make_user():
    # user with both google tokens set, individual tests override fields
    u = MagicMock()
    u.id = uuid4()
    u.calendar_token = "cal-tok"
    u.gmail_token = "gmail-tok"
    return u


def test_calendar_step_injects_access_token():
    user = _make_user()
    cal_mock = MagicMock()
    cal_mock.execute.return_value = [{"id": "evt_1"}]
    plan = {
        "plan_steps": [
            {"tool": "calendar_tool", "params": {"operation": "read"}, "status": "PENDING"}
        ]
    }

    with patch.dict(TOOL_REGISTRY, {"calendar_tool": cal_mock}):
        results = run_plan(plan, user)

    call_params = cal_mock.execute.call_args[0][0]
    assert call_params["access_token"] == "cal-tok"  # injected from user
    assert call_params["operation"] == "read"  # original params preserved
    assert results[0]["status"] == "ok"


def test_gmail_step_injects_gmail_token():
    # gmail_tool should get gmail_token specifically, not calendar_token
    user = _make_user()
    gmail_mock = MagicMock()
    plan = {
        "plan_steps": [
            {"tool": "gmail_tool", "params": {"operation": "read"}, "status": "PENDING"}
        ]
    }

    with patch.dict(TOOL_REGISTRY, {"gmail_tool": gmail_mock}):
        run_plan(plan, user)

    assert gmail_mock.execute.call_args[0][0]["access_token"] == "gmail-tok"


def test_sms_step_no_token_injection():
    # non-google tools shouldn't have access_token in their params
    user = _make_user()
    sms_mock = MagicMock()
    plan = {
        "plan_steps": [
            {"tool": "sms_tool", "params": {"to": "+1", "body": "hi"}, "status": "PENDING"}
        ]
    }

    with patch.dict(TOOL_REGISTRY, {"sms_tool": sms_mock}):
        run_plan(plan, user)

    call_params = sms_mock.execute.call_args[0][0]
    assert "access_token" not in call_params
    assert call_params == {"to": "+1", "body": "hi"}


def test_missing_calendar_token_no_injection():
    # if user has no calendar_token yet (oauth not done), don't inject None
    user = _make_user()
    user.calendar_token = None
    cal_mock = MagicMock()
    plan = {
        "plan_steps": [
            {"tool": "calendar_tool", "params": {"operation": "read"}, "status": "PENDING"}
        ]
    }

    with patch.dict(TOOL_REGISTRY, {"calendar_tool": cal_mock}):
        run_plan(plan, user)

    assert "access_token" not in cal_mock.execute.call_args[0][0]


def test_unknown_tool_skipped_not_raised():
    # claude sometimes hallucinates tool names, and it shouldn't 500 the webhook
    user = _make_user()
    sms_mock = MagicMock()
    plan = {
        "plan_steps": [
            {"tool": "weather_tool", "params": {}, "status": "PENDING"},
            {"tool": "sms_tool", "params": {"to": "+1", "body": "hi"}, "status": "PENDING"},
        ]
    }

    with patch.dict(TOOL_REGISTRY, {"sms_tool": sms_mock}):
        results = run_plan(plan, user)

    assert results[0]["status"] == "skipped"
    assert results[0]["tool"] == "weather_tool"
    sms_mock.execute.assert_called_once()  # the next step still ran


# [GenAI Use] Prompt: "show me how to test that dispatch.run_plan keeps going
# when one tool raises during execute(). i want the first step (calendar_tool)
# to raise google 401, the second step (sms_tool) to still execute, and the
# results list to reflect both: error on step 0, ok on step 1."
# [GenAI Use] LLM Response Start
def test_tool_exception_caught_loop_continues():
    # one bad call (eg google 401) shouldn't kill remaining steps
    user = _make_user()
    cal_mock = MagicMock()
    cal_mock.execute.side_effect = RuntimeError("Google 401")
    sms_mock = MagicMock()
    plan = {
        "plan_steps": [
            {"tool": "calendar_tool", "params": {"operation": "read"}, "status": "PENDING"},
            {"tool": "sms_tool", "params": {"to": "+1", "body": "fallback"}, "status": "PENDING"},
        ]
    }

    with patch.dict(TOOL_REGISTRY, {"calendar_tool": cal_mock, "sms_tool": sms_mock}):
        results = run_plan(plan, user)

    assert results[0]["status"] == "error"
    assert "Google 401" in results[0]["error"]
    assert results[1]["status"] == "ok"  # sms still ran
# [GenAI Use] LLM Response End
# [GenAI Use] Reflection: i wouldn't have remembered MagicMock.side_effect can be
# an exception class, i thought you had to use a wrapper. tested by hand and it
# works. tweaked the wording on the error message check to match what dispatch
# actually formats ("Google 401" substring).


def test_empty_plan_steps_no_op():
    # conversational-only plans have no steps to run
    user = _make_user()
    assert run_plan({"plan_steps": []}, user) == []
    assert run_plan({}, user) == []  # missing key entirely


# [GenAI Use] Prompt: "give me a test that proves run_plan doesn't mutate the
# caller's plan dict during token injection. the worry is that we'd accidentally
# write access_token into plan['plan_steps'][i]['params'] and then later code
# that logs or persists the plan would leak the token. assert the original
# dict is clean after run_plan returns."
# [GenAI Use] LLM Response Start
def test_caller_plan_not_mutated():
    # injection happens on a copy -- access_token shouldn't leak back into
    # the caller's plan dict (might get logged/persisted elsewhere later)
    user = _make_user()
    cal_mock = MagicMock()
    plan = {
        "plan_steps": [
            {"tool": "calendar_tool", "params": {"operation": "read"}, "status": "PENDING"}
        ]
    }

    with patch.dict(TOOL_REGISTRY, {"calendar_tool": cal_mock}):
        run_plan(plan, user)

    assert "access_token" not in plan["plan_steps"][0]["params"]
# [GenAI Use] LLM Response End
# [GenAI Use] Reflection: this one i never would have thought to write. caught
# it would matter when claude pointed out we log the full plan dict in webhook
# logs and on a celery push (eventually). if injection mutated the caller's
# dict the access_token would end up in supabase audit logs.


def test_call_tool_routes_through_notify_user():
    # when claude emits call_tool in a plan step, dispatch should hit
    # notify_user so the call actually goes out to the user's number (not
    # to whatever claude hallucinated in params['to']) and outbound gets logged
    user = _make_user()
    user.phone_number = "+13105550199"
    db = MagicMock()
    plan = {
        "plan_steps": [
            {"tool": "call_tool",
             "params": {"message": "reminder: pick up kids at 3"},
             "status": "PENDING"}
        ]
    }

    with patch("services.dispatch.notify_user") as notify_mock:
        notify_mock.return_value = {"status": "ok", "sid": "CA1", "channel": "call"}
        results = run_plan(plan, user, db)

    notify_mock.assert_called_once_with(
        db, user,
        message="reminder: pick up kids at 3",
        channel="call",
        force=True,  # active conversation -> bypass quiet hours
    )
    assert results[0]["status"] == "ok"


def test_sms_tool_routes_through_notify_user():
    user = _make_user()
    db = MagicMock()
    plan = {
        "plan_steps": [
            {"tool": "sms_tool",
             "params": {"to": "+1", "body": "remember to call mom"},
             "status": "PENDING"}
        ]
    }

    with patch("services.dispatch.notify_user") as notify_mock:
        notify_mock.return_value = {"status": "ok", "sid": "SM1", "channel": "sms"}
        run_plan(plan, user, db)

    # notify_user uses user.phone_number, not claude's params['to'] -- prevents
    # claude from accidentally texting some other number from the conversation
    assert notify_mock.call_args.kwargs["message"] == "remember to call mom"
    assert notify_mock.call_args.kwargs["channel"] == "sms"
    assert notify_mock.call_args.kwargs["force"] is True


def test_call_tool_with_scheduled_at_enqueues_with_eta():
    # "call me at 6:55" -> claude returns absolute scheduled_at. dispatch
    # parses + hands to apply_async(eta=...). nothing fires inline.
    from datetime import datetime, timedelta, timezone
    user = _make_user()
    db = MagicMock()
    future = datetime.now(timezone.utc) + timedelta(minutes=7)
    plan = {
        "plan_steps": [
            {"tool": "call_tool",
             "params": {"message": "reminder", "scheduled_at": future.isoformat()},
             "status": "PENDING"}
        ]
    }

    with patch("services.dispatch.notify_user_task") as task_mock, \
         patch("services.dispatch.notify_user") as notify_mock:
        results = run_plan(plan, user, db)

    notify_mock.assert_not_called()
    task_mock.apply_async.assert_called_once()
    kwargs = task_mock.apply_async.call_args.kwargs
    assert kwargs["args"] == [str(user.id), "reminder", "call"]
    # eta is a tz-aware datetime parsed from the iso string
    assert kwargs["eta"] == future
    assert results[0]["status"] == "scheduled"


def test_call_tool_without_scheduled_at_fires_immediately():
    # no scheduled_at -> immediate via notify_user (today's behavior)
    user = _make_user()
    db = MagicMock()
    plan = {
        "plan_steps": [
            {"tool": "call_tool",
             "params": {"message": "now"},
             "status": "PENDING"}
        ]
    }

    with patch("services.dispatch.notify_user_task") as task_mock, \
         patch("services.dispatch.notify_user") as notify_mock:
        notify_mock.return_value = {"status": "ok", "sid": "CA1"}
        run_plan(plan, user, db)

    task_mock.apply_async.assert_not_called()
    notify_mock.assert_called_once()


def test_scheduled_at_in_past_still_enqueues():
    # if claude misreads and emits a past time, we let celery run it
    # immediately rather than rolling forward 24h. proves we don't crash.
    from datetime import datetime, timedelta, timezone
    user = _make_user()
    db = MagicMock()
    past = datetime.now(timezone.utc) - timedelta(minutes=10)
    plan = {
        "plan_steps": [
            {"tool": "sms_tool",
             "params": {"body": "oops", "scheduled_at": past.isoformat()},
             "status": "PENDING"}
        ]
    }

    with patch("services.dispatch.notify_user_task") as task_mock, \
         patch("services.dispatch.notify_user"):
        run_plan(plan, user, db)

    task_mock.apply_async.assert_called_once()
    assert task_mock.apply_async.call_args.kwargs["eta"] == past


def test_sms_tool_falls_back_to_direct_adapter_without_db():
    # back-compat: callers that don't pass db should still use the registry path
    user = _make_user()
    sms_mock = MagicMock()
    plan = {
        "plan_steps": [
            {"tool": "sms_tool",
             "params": {"to": "+1", "body": "hi"},
             "status": "PENDING"}
        ]
    }

    with patch.dict(TOOL_REGISTRY, {"sms_tool": sms_mock}), \
         patch("services.dispatch.notify_user") as notify_mock:
        run_plan(plan, user)  # no db

    sms_mock.execute.assert_called_once()
    notify_mock.assert_not_called()


def test_multiple_steps_in_order():
    # claude might say "read calendar then send sms" -- order matters
    user = _make_user()
    call_order = []
    cal_mock = MagicMock()
    cal_mock.execute.side_effect = lambda p: call_order.append("cal")
    sms_mock = MagicMock()
    sms_mock.execute.side_effect = lambda p: call_order.append("sms")
    plan = {
        "plan_steps": [
            {"tool": "calendar_tool", "params": {"operation": "read"}, "status": "PENDING"},
            {"tool": "sms_tool", "params": {"to": "+1", "body": "x"}, "status": "PENDING"},
        ]
    }

    with patch.dict(TOOL_REGISTRY, {"calendar_tool": cal_mock, "sms_tool": sms_mock}):
        run_plan(plan, user)

    assert call_order == ["cal", "sms"]
