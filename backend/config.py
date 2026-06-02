#env + app settings. add new creds here.
#usage: from config import settings; settings.DATABASE_URL
#legacy TWILIO_AUTH_TOKEN const kept for backcompat.

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    #db -- supabase tx pooler uri (port 6543)
    #fmt: postgresql+psycopg2://USER:PWD@HOST:PORT/postgres
    DATABASE_URL: str = ""

    #supabase rest/auth/storage (postgres goes via DATABASE_URL above)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    #twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""  #e164, e.g. +13105550199

    #llm
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""  #fallback

    #stt
    DEEPGRAM_API_KEY: str = ""

    #google api -- calendar + gmail oauth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    #celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    #auth
    JWT_SECRET: str = "change-me-in-production"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    #misc
    APP_ENV: str = "development"  #dev | staging | prod
    LOG_LEVEL: str = "INFO"


settings = Settings()


#backcompat: existing code does `from config import TWILIO_AUTH_TOKEN`.
#new code should use `settings.TWILIO_AUTH_TOKEN`.
TWILIO_AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
