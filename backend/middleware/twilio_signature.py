import base64
import hashlib
import hmac


def validate_twilio_signature(
    auth_token: str,
    signature_header: str | None,
    url: str,
    params: dict[str, str] | None = None,
) -> bool:
    """Return True iff `signature_header` is a valid Twilio signature.

    `url` must be the full URL Twilio called (scheme, host, path, query).
    `params` is the form-encoded POST body, or None for GET / JSON requests.
    """
    if not signature_header:
        return False

    payload = url
    if params:
        for key in sorted(params):
            payload += key + params[key]

    digest = hmac.new(
        auth_token.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    expected = base64.b64encode(digest).decode("utf-8")

    return hmac.compare_digest(expected, signature_header)
