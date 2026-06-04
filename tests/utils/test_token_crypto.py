#unit tests for utils.token_crypto.
#covers the encrypt -> store -> retrieve -> decrypt round-trip required by
#the security-compliance TODO in models/user.py, plus the failure modes
#we care about (tamper detection, missing-key misconfig, key rotation
#via MultiFernet). db interactions are mocked -- the round-trip uses a
#dict to stand in for the google_oauth JSONB column.

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from config import settings
from utils import token_crypto
from utils.token_crypto import (
    TokenCryptoError,
    decrypt_token,
    encrypt_token,
    generate_key,
    reset_cipher_cache,
)


@pytest.fixture
def fresh_key(monkeypatch):
    #fresh fernet key per test, cache cleared so prior tests don't leak
    #their cipher into ours. yields the key so tests can assert on it.
    key = generate_key()
    monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", key)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    reset_cipher_cache()
    yield key
    reset_cipher_cache()


# ── primitives ─────────────────────────────────────────────────


def test_encrypt_decrypt_round_trip(fresh_key):
    #the core contract: plaintext -> ciphertext -> plaintext is identity.
    plaintext = "ya29.a0ARrdaM-fake-google-access-token"
    ct = encrypt_token(plaintext)
    assert ct != plaintext
    assert decrypt_token(ct) == plaintext


def test_ciphertext_is_nondeterministic(fresh_key):
    #fernet embeds a fresh iv per call -- two encrypts of the same
    #plaintext must produce different ciphertexts but both decrypt back.
    ct1 = encrypt_token("same-token")
    ct2 = encrypt_token("same-token")
    assert ct1 != ct2
    assert decrypt_token(ct1) == "same-token"
    assert decrypt_token(ct2) == "same-token"


def test_encrypt_none_passes_through(fresh_key):
    #refresh_token is optional in the oauth bundle; None must round-trip.
    assert encrypt_token(None) is None
    assert decrypt_token(None) is None


def test_decrypt_tampered_ciphertext_raises(fresh_key):
    #fernet is authenticated -- flipping a byte must fail decrypt.
    ct = encrypt_token("real-token")
    tampered = ct[:-2] + ("AA" if ct[-2:] != "AA" else "BB")
    with pytest.raises(TokenCryptoError):
        decrypt_token(tampered)


def test_decrypt_with_wrong_key_raises(monkeypatch):
    #ciphertext from key A must not decrypt under key B.
    monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", generate_key())
    monkeypatch.setattr(settings, "APP_ENV", "development")
    reset_cipher_cache()
    ct = encrypt_token("secret")

    monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", generate_key())
    reset_cipher_cache()
    with pytest.raises(TokenCryptoError):
        decrypt_token(ct)


def test_missing_key_raises(monkeypatch):
    #empty config = hard fail, never silently no-op.
    monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", "")
    monkeypatch.setattr(settings, "APP_ENV", "development")
    reset_cipher_cache()
    with pytest.raises(TokenCryptoError):
        encrypt_token("x")


def test_dev_placeholder_rejected_outside_development(monkeypatch):
    #safety net so a forgotten .env doesn't ship the public dev key to prod.
    monkeypatch.setattr(
        settings,
        "TOKEN_ENCRYPTION_KEY",
        "dev-only-insecure-key-please-override-in-env",
    )
    monkeypatch.setattr(settings, "APP_ENV", "production")
    reset_cipher_cache()
    with pytest.raises(TokenCryptoError):
        encrypt_token("x")


def test_key_rotation_via_multifernet(monkeypatch):
    #encrypt under old key, then rotate by prepending new key. decrypt
    #must still succeed (old key still in the ring) and a fresh encrypt
    #must produce ciphertext that the OLD key alone cannot decrypt.
    old_key = generate_key()
    monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", old_key)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    reset_cipher_cache()
    legacy_ct = encrypt_token("legacy-token")

    new_key = generate_key()
    monkeypatch.setattr(settings, "TOKEN_ENCRYPTION_KEY", f"{new_key},{old_key}")
    reset_cipher_cache()
    assert decrypt_token(legacy_ct) == "legacy-token"

    rotated_ct = encrypt_token("legacy-token")
    #old key alone must not decrypt the new ciphertext.
    from cryptography.fernet import InvalidToken
    with pytest.raises(InvalidToken):
        Fernet(old_key.encode()).decrypt(rotated_ct.encode())


# ── service-layer integration: store + retrieve via google_oauth JSONB ──


def test_service_round_trip_via_save_and_get(monkeypatch, fresh_key):
    #end-to-end: save_google_oauth encrypts, get_google_oauth decrypts,
    #and the value sitting on the User row in between is ciphertext.
    from services import user_service

    fake_user = MagicMock()
    fake_user.google_oauth = None
    monkeypatch.setattr(
        user_service, "get_user_by_id", lambda db, uid: fake_user
    )

    db = MagicMock()
    user_id = uuid4()
    access = "ya29.access-plain"
    refresh = "1//refresh-plain"
    expiry = "2030-01-01T00:00:00"

    user_service.save_google_oauth(db, user_id, access, refresh, expiry)

    stored = fake_user.google_oauth
    #at-rest invariant -- nothing on the row may look like the plaintext.
    assert stored["access_token"] != access
    assert stored["refresh_token"] != refresh
    assert stored["expiry"] == expiry

    out = user_service.get_google_oauth(db, user_id)
    assert out == {
        "access_token": access,
        "refresh_token": refresh,
        "expiry": expiry,
    }


def test_service_preserves_existing_refresh_token_when_not_resupplied(
    monkeypatch, fresh_key
):
    #google's refresh response doesn't re-issue refresh_token. save with
    #refresh=None should keep the existing ciphertext untouched (no
    #double-wrap) and still decrypt back to the original plaintext.
    from services import user_service

    fake_user = MagicMock()
    fake_user.google_oauth = {
        "access_token": encrypt_token("old-access"),
        "refresh_token": encrypt_token("keep-me"),
        "expiry": "2030-01-01T00:00:00",
    }
    prior_refresh_ct = fake_user.google_oauth["refresh_token"]
    monkeypatch.setattr(
        user_service, "get_user_by_id", lambda db, uid: fake_user
    )

    user_service.save_google_oauth(
        MagicMock(), uuid4(), "new-access", None, "2031-01-01T00:00:00"
    )

    assert fake_user.google_oauth["refresh_token"] == prior_refresh_ct
    out = user_service.get_google_oauth(MagicMock(), uuid4())
    assert out["refresh_token"] == "keep-me"
    assert out["access_token"] == "new-access"
