#cloud run image for g backend.
#build + deploy:
#  gcloud builds submit --tag gcr.io/PROJECT_ID/g-backend ./backend
#  gcloud run deploy g-backend --image gcr.io/PROJECT_ID/g-backend --region us-west1 --allow-unauthenticated

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

#psycopg2 needs libpq; build-essential only at install time
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

#deps first -> layer cache survives code edits
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . ./

#cloud run injects $PORT (default 8080). bind 0.0.0.0.
ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips="*"
