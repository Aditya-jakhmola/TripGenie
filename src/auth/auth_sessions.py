"""
Stateless auth sessions: a signed, tamper-proof token carries the user id
and an expiry timestamp directly, instead of a server-side session store.
This means login survives server restarts automatically (a very common
part of the dev workflow) without needing a database table or any
in-memory state that could be lost.
"""

import base64
import hashlib
import hmac
import json
import time

from src.config.settings import AUTH_SECRET_KEY, AUTH_SESSION_TTL_SECONDS


def _sign(payload: bytes) -> str:
    if not AUTH_SECRET_KEY:
        # Signing with an empty key would produce tokens anyone could forge.
        raise RuntimeError(
            "AUTH_SECRET_KEY is not set. Add a long random value to your .env file."
        )

    signature = hmac.new(
        AUTH_SECRET_KEY.encode("utf-8"), payload, hashlib.sha256
    ).digest()

    return base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")


def create_auth_session(user_id: int) -> str:
    data = {"uid": user_id, "exp": time.time() + AUTH_SESSION_TTL_SECONDS}
    payload = json.dumps(data, separators=(",", ":")).encode("utf-8")

    encoded_payload = base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")
    signature = _sign(payload)

    return f"{encoded_payload}.{signature}"


def get_user_id_for_token(token: str):
    # With no secret configured nothing can be verified, so nobody is logged in.
    if not AUTH_SECRET_KEY:
        return None

    if not token or "." not in token:
        return None

    encoded_payload, signature = token.rsplit(".", 1)

    try:
        padded = encoded_payload + "=" * (-len(encoded_payload) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("utf-8"))
    except Exception:
        return None

    expected_signature = _sign(payload)

    # Compare as bytes: compare_digest raises on non-ASCII str, and the
    # token comes straight from a client-controlled cookie.
    if not hmac.compare_digest(
        signature.encode("utf-8", "replace"),
        expected_signature.encode("utf-8"),
    ):
        return None

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        return None

    if time.time() > data.get("exp", 0):
        return None

    return data.get("uid")


def delete_auth_session(token: str) -> None:
    # Stateless tokens can't be revoked server-side without a blocklist.
    # Logging out just clears the cookie client-side (see app.py) -
    # fine for this app's scale.
    pass