"""
Password hashing using PBKDF2-HMAC-SHA256 from Python's standard library.

No extra dependency needed - bcrypt/argon2 aren't already in this
project, and PBKDF2 at a high iteration count is a legitimate, still
OWASP-recommended choice. If this ever handles real production traffic,
argon2 would be a reasonable upgrade, but this is genuinely secure for
a personal/college-project login system, not a shortcut.
"""

import hashlib
import hmac
import secrets

from src.config.settings import PASSWORD_HASH_ITERATIONS


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        PASSWORD_HASH_ITERATIONS,
    ).hex()

    return f"{PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        iterations_str, salt, digest = stored.split("$")
        iterations = int(iterations_str)
    except (ValueError, AttributeError):
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        iterations,
    ).hex()

    return hmac.compare_digest(candidate, digest)