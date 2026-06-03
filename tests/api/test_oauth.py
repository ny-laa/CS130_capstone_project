import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))
from unittest.mock import MagicMock, patch
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


@patch("api.auth.oauth.save_google_oauth")
@patch("api.auth.oauth.create_user")
@patch("api.auth.oauth.get_user_by_email")
@patch("api.auth.oauth.httpx.AsyncClient")

# Used claude to generate the following tests
def test_oauth_callback_creates_new_user(
    mock_http, mock_get_email, mock_create, mock_save
):
    # simulate google returning tokens
    mock_http.return_value.__aenter__.return_value.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "access_token": "fake-access",
            "refresh_token": "fake-refresh",
            "expires_in": 3600,
            # minimal valid id_token (header.payload.sig) — payload is base64 of {"email":"test@example.com","name":"Test User"}
            "id_token": "x.eyJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJuYW1lIjoiVGVzdCBVc2VyIn0.x",
        },
    )
    mock_get_email.return_value = None  # user doesn't exist yet
    fake_user = MagicMock(id=uuid4())
    mock_create.return_value = fake_user

    response = client.get("/oauth/google?code=fake-code", follow_redirects=False)

    assert response.status_code == 307  # redirect to frontend
    mock_create.assert_called_once()
    mock_save.assert_called_once()


@patch("api.auth.oauth.save_google_oauth")
@patch("api.auth.oauth.get_user_by_email")
@patch("api.auth.oauth.httpx.AsyncClient")
def test_oauth_callback_updates_existing_user(mock_http, mock_get_email, mock_save):
    # user already exists — should not create a new one
    mock_http.return_value.__aenter__.return_value.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "access_token": "fake-access",
            "refresh_token": "fake-refresh",
            "expires_in": 3600,
            "id_token": "x.eyJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJuYW1lIjoiVGVzdCBVc2VyIn0.x",
        },
    )
    fake_user = MagicMock(id=uuid4())
    mock_get_email.return_value = fake_user  # user already exists

    response = client.get("/oauth/google?code=fake-code", follow_redirects=False)

    assert response.status_code == 307
    mock_save.assert_called_once()


@patch("api.auth.oauth.httpx.AsyncClient")
def test_oauth_callback_400_on_google_error(mock_http):
    # google rejects the code exchange
    mock_http.return_value.__aenter__.return_value.post.return_value = MagicMock(
        status_code=400,
        text="invalid_grant",
    )

    response = client.get("/oauth/google?code=bad-code", follow_redirects=False)
    assert response.status_code == 400

# end of claude tests