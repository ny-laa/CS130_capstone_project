# G — backend

FastAPI service. Talks to Supabase (Postgres), Twilio (SMS + voice), Anthropic
(LLM), Deepgram (STT), and Google (Calendar + Gmail). Deployed to Google Cloud
Run.

## Quick start (local)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in DATABASE_URL (Supabase pooler URI) at minimum; everything else is optional for local dev unless you're touching that subsystem.

uvicorn main:app --reload
# -> http://localhost:8000/health         -> {"status":"ok"}
# -> http://localhost:8000/health/db      -> confirms Supabase reachable
# -> http://localhost:8000/docs           -> OpenAPI/Swagger UI
```

If you're testing Twilio webhooks locally, also run `--proxy-headers
--forwarded-allow-ips="*"` and tunnel with ngrok

## Database (Supabase)

Two ways to create the schema:

**Option A — paste SQL**:

1. Open your Supabase project -> SQL Editor -> "+ New query"
2. Paste the contents of `migrations/initial_schema.sql`
3. Run

**Option B — Alembic** (use for ongoing schema changes):

```bash
# from backend/
alembic revision --autogenerate -m "init schema"   # creates a versioned migration in migrations/versions/
alembic upgrade head                               # applies it to the DB in DATABASE_URL
```

After migration there should be four tables in the `public`
schema: `users`, `tasks`, `messages`, `preferences`.

## Deploy to Cloud Run

Prereqs: `gcloud` CLI installed + authenticated, project created, billing
enabled, and the Cloud Run + Cloud Build APIs enabled.

```bash
# from backend/
gcloud config set project YOUR_PROJECT_ID
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/g-backend .
gcloud run deploy g-backend \
    --image gcr.io/YOUR_PROJECT_ID/g-backend \
    --region us-west1 \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars APP_ENV=production \
    --set-secrets DATABASE_URL=DATABASE_URL:latest,TWILIO_AUTH_TOKEN=TWILIO_AUTH_TOKEN:latest
```

Store secrets in Secret Manager first (`gcloud secrets create DATABASE_URL
--data-file -`), then reference them with `--set-secrets`. Never bake secrets
into the image.

## Layout

```
backend/
  main.py              FastAPI app + /health + /health/db
  config.py            Pydantic settings, loads .env
  database.py          SQLAlchemy engine + SessionLocal + Base + get_db()
  Dockerfile           Cloud Run container
  alembic.ini          migration tool config
  migrations/
    env.py             alembic runtime hook (uses our settings + Base)
    initial_schema.sql one-shot SQL alternative to alembic
    versions/          generated migrations (don't hand-edit)
  models/              SQLAlchemy ORM classes (User, Task, Message, Preference)
  schemas/             pydantic request/response schemas
  services/            business logic on top of models
  api/                 FastAPI routers
    webhooks/          /webhooks/sms, /webhooks/call
    auth/              /auth/google/callback (OAuth)
  adapters/            external service wrappers (llm, twilio, google, deepgram)
  orchestrator/        LangChain agent + task planner + escalation engine
  workers/             celery app + task runner
  middleware/          twilio signature validation
```

## Testing

```bash
# from project root
pytest tests -v
```
