# celery instance for G. broker + backend point at the redis instance
# configured in settings (CELERY_BROKER_URL / CELERY_RESULT_BACKEND).
#
# Local setup:
#   redis:  brew services start redis   (or `docker run -d -p 6379:6379 redis`)
#   worker: cd backend && celery -A workers.celery_app worker --loglevel=info
#
# Sanity check (with redis + worker running):
#   cd backend && python -c "from workers.celery_app import ping; \
#       print(ping.delay().get(timeout=5))"   # -> "pong"
#
# Currently the only Celery use is delayed notifications -- dispatch routes
# sms_tool / call_tool plan steps that carry `delay_seconds` here via
# notify_user_task.apply_async(countdown=N). Pending tasks live in redis so
# they survive uvicorn restarts (the gap that motivated this in the first
# place). Elliot's TaskRunner / orchestrator is not wrapped here yet -- that's
# a follow-up when persistence + the JSON->Task conversion are ready.

from celery import Celery
from celery.schedules import crontab

from config import settings

app = Celery(
    "g",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "workers.tasks.notifications",
        "workers.tasks.morning_digest",
        "workers.tasks.plan_step",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # prototype digest schedule uses LA time for now, later can expand for user specific timezones + digest times
    timezone="America/Los_Angeles",
    enable_utc=True,
    beat_schedule={
    "send-morning-digests-every-day": {
        "task": "send_morning_digests",
        "schedule": crontab(hour=8, minute=0),
    },
},
)


@app.task(name="ping")
def ping() -> str:
    # liveness check -- doesn't touch twilio / db. used to verify the worker
    # is actually consuming from the queue.
    return "pong"
