# google oauth callback route
# after user authenticates on the frontend we get the token here and save it
# this is how G gets access to google calendar and gmail
# used docs at https://developers.google.com/identity/protocols/oauth2, https://fastapi.tiangolo.com/,
# https://docs.python.org/3/library/base64.html for info on how to implement this file
# Claude gave me the following structure for the file:
# Route definition — GET /oauth/google receives the code Google sends back
# Token exchange — POST to Google with the code, get back access/refresh tokens
# User decode — pull email/name out of the id_token JWT
# Upsert user — find existing user or create new one in DB
# Save tokens — store access_token, refresh_token, expiry in google_oauth column
# Redirect — send user back to frontend

import base64, json, httpx
from datetime import datetime, timedelta

# Claude told me the following imports I should use for this file
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from config import settings
from database import get_db
from services.user_service import get_user_by_email, create_user, save_google_oauth

router = APIRouter()

GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
# callback route for oauth
@router.get("/oauth/google")

async def google_oauth(
    # fastapi extracting code and injecting db
    code: str,
    db: Session = Depends(get_db),
):

    async with httpx.AsyncClient() as client:
        # get the token response data
        response = await client.post(
            GOOGLE_TOKEN,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        # error handling
    if response.status_code != 200:
        raise HTTPException(
            status_code = 400
        )

    token = response.json()

    # get user from token
    id_token = token["id_token"]
    payload_b64 = id_token.split(".")[1]
    payload = base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4))
    # get user information (name/email)
    user_info = json.loads(payload)
    email = user_info["email"]
    name = user_info.get("name")
    user = get_user_by_email(db, email)

    # add user to database
    if not user:
        user = create_user(db, phone_number=f"pending_{email}", email=email, name=name)

    # save tokens and expire in 1 hour
    expire = datetime.utcnow() + timedelta(seconds=token["expires_in"])
    save_google_oauth(
        db,
        user_id=user.id,
        access_token= token["access_token"],
        refresh_token= token.get("refresh_token"),
        expiry= expire.isoformat()
    )
    
    return RedirectResponse(url="http://localhost:5173?auth=success")
