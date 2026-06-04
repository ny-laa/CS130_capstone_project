#fastapi entry. registers routes.
#local: uvicorn main:app --reload
#cloud run: Dockerfile binds 0.0.0.0:$PORT

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.auth.routes import router as auth_router
from api.chat import router as chat_router
from api.contacts import router as contacts_router
from api.family_members import router as family_members_router
from api.providers import router as providers_router
from api.users import router as users_router
from api import tasks as tasks_api
from api.webhooks import call, sms
from config import settings
from database import get_db

from api.auth.oauth import router as oauth_router
from api.chat import router as chat_router

app = FastAPI(
    title="G",
    description="parent's personal ai secretary -- backend",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    # any localhost port -- Vite auto-increments past 5173 if that's busy,
    # and we don't want to chase ports in this file every time. regex
    # matches http(s)://localhost:<digits>.
    allow_origin_regex=r"https?://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(chat_router)
app.include_router(family_members_router)
app.include_router(contacts_router)
app.include_router(providers_router)
app.include_router(sms.router)
app.include_router(call.router)
app.include_router(tasks_api.router)
app.include_router(oauth_router)
app.include_router(chat_router)

# Debug endpoints for manually firing outbound tools. Only mounted when
# DEBUG=true so they can't be hit in prod by accident.
if os.getenv("DEBUG", "").lower() == "true":
    from api import debug
    app.include_router(debug.router)


@app.get("/")
def root() -> dict:
    #default cloud run service-url check
    return {"service": "g-backend", "env": settings.APP_ENV, "status": "ok"}


@app.get("/health")
def health() -> dict:
    #liveness. no db touch -> fast even if pg is down.
    return {"status": "ok"}


#[GenAI Use] Prompt: Write a FastAPI route GET /health/db that takes in a
#SQLAlchemy Session via Depends(get_db), runs a simple query to count the number of tables
#in the public schema, and returns a json dict with the count and a status ok.
#[GenAI Use] LLM response:
@app.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict:
    #readiness. counts public tables as a connectivity sanity check.
    result = db.execute(
        text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
    ).scalar_one()
    return {"status": "ok", "public_table_count": result}
#[GenAI Use] Response end
#[GenAI Use] Reflect: I believe this is correct after looking at the code and running
#some tests.
