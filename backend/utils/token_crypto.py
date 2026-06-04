#symmetric encryption helpers for oauth tokens at rest.
#used by services.user_service to wrap access_token / refresh_token before
#they hit the google_oauth JSONB column on the users row, and to unwrap on
#read. ciphertext is url-safe base64 ASCII so it slots straight into JSONB
#with zero schema changes.
#
#why MultiFernet: lets us rotate keys without a bulk re-encrypt. settings
#exposes TOKEN_ENCRYPTION_KEY as a comma-separated list -- newest key
#first; older keys are kept so existing ciphertext still decrypts until
#the next save_google_oauth call re-encrypts under the current primary.
#
#fernet = AES-128-CBC + HMAC-SHA256, authenticated. tamper / wrong-key
#raises InvalidToken; we surface that as ValueError to callers so the
#service layer error contract stays consistent.

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from config import settings


#sentinel value config.py ships as the dev default. refuse to use it
#outside APP_ENV=development so a forgotten .env never silently
#encrypts prod tokens under a public key.
_DEV_PLACEHOLDER = "dev-only-insecure-key-please-override-in-env"


class TokenCryptoError(ValueError):
    #raised on decrypt failure (tamper, wrong key, corrupted blob) and on
    #misconfiguration (missing / placeholder key in non-dev env).
    pass


def generate_key() -> str:
    #convenience for ops -- run `python -c "from utils.token_crypto import
    #generate_key; print(generate_key())"` to mint a new key for the env.
    return Fernet.generate_key().decode("ascii")


@lru_cache(maxsize=1)
def _cipher() -> MultiFernet:
    #cached so we don't rebuild Fernet on every encrypt/decrypt call.
    #tests that swap settings.TOKEN_ENCRYPTION_KEY should call
    #reset_cipher_cache() after mutating settings.
    raw = settings.TOKEN_ENCRYPTION_KEY or ""
    keys = [k.strip() for k in raw.split(",") if k.strip()]

    if not keys:
        raise TokenCryptoError("TOKEN_ENCRYPTION_KEY is not configured")

    if settings.APP_ENV != "development" and _DEV_PLACEHOLDER in keys:
        raise TokenCryptoError(
            "TOKEN_ENCRYPTION_KEY is still the dev placeholder; "
            "set a real key before running outside development"
        )

    fernets = []
    for k in keys:
        try:
            fernets.append(Fernet(k.encode("ascii")))
        except (ValueError, TypeError) as exc:
            raise TokenCryptoError(f"invalid fernet key in TOKEN_ENCRYPTION_KEY: {exc}") from exc

    return MultiFernet(fernets)


def reset_cipher_cache() -> None:
    #test hook -- clears the lru_cache so a fresh settings snapshot is read
    #on the next encrypt/decrypt call.
    _cipher.cache_clear()


def encrypt_token(plaintext: str) -> str:
    #encrypts under the primary (first) key. None passes through so callers
    #can hand us optional refresh_token without a guard at every site.
    if plaintext is None:
        return None
    if not isinstance(plaintext, str):
        raise TokenCryptoError("encrypt_token expects a str")
    return _cipher().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_token(ciphertext: str) -> str:
    #tries every key in the MultiFernet ring; InvalidToken means none of
    #them decrypt cleanly -> surface as TokenCryptoError (a ValueError).
    if ciphertext is None:
        return None
    if not isinstance(ciphertext, str):
        raise TokenCryptoError("decrypt_token expects a str")
    try:
        return _cipher().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise TokenCryptoError("token decrypt failed -- tampered or wrong key") from exc
