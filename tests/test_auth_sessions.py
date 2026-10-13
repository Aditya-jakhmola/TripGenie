import base64
import json
import re
import time
import unittest
from unittest.mock import patch

from src.auth import auth_sessions


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


class AuthSessionTests(unittest.TestCase):
    def setUp(self):
        for name, value in [
            ("AUTH_SECRET_KEY", "test-secret"),
            ("AUTH_SESSION_TTL_SECONDS", 3600),
        ]:
            patcher = patch.object(auth_sessions, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_token_round_trips_to_the_same_user(self):
        token = auth_sessions.create_auth_session(42)
        self.assertEqual(auth_sessions.get_user_id_for_token(token), 42)

    def test_different_users_get_different_tokens(self):
        a = auth_sessions.create_auth_session(1)
        b = auth_sessions.create_auth_session(2)
        self.assertNotEqual(a, b)
        self.assertEqual(auth_sessions.get_user_id_for_token(a), 1)
        self.assertEqual(auth_sessions.get_user_id_for_token(b), 2)

    def test_token_only_uses_cookie_safe_characters(self):
        token = auth_sessions.create_auth_session(7)
        self.assertRegex(token, r"^[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+$")

    def test_forged_payload_with_a_borrowed_signature_is_rejected(self):
        # An attacker keeps user 1's signature but swaps in user 2's payload.
        _, signature = auth_sessions.create_auth_session(1).rsplit(".", 1)
        forged = json.dumps({"uid": 2, "exp": time.time() + 9999}, separators=(",", ":"))
        self.assertIsNone(
            auth_sessions.get_user_id_for_token(f"{_b64(forged.encode())}.{signature}")
        )

    def test_tampered_signature_is_rejected(self):
        payload, signature = auth_sessions.create_auth_session(1).rsplit(".", 1)
        flipped = ("A" if signature[-1] != "A" else "B")
        self.assertIsNone(
            auth_sessions.get_user_id_for_token(f"{payload}.{signature[:-1]}{flipped}")
        )

    def test_token_signed_with_another_secret_is_rejected(self):
        token = auth_sessions.create_auth_session(1)
        with patch.object(auth_sessions, "AUTH_SECRET_KEY", "a-different-secret"):
            self.assertIsNone(auth_sessions.get_user_id_for_token(token))

    def test_expired_token_is_rejected(self):
        with patch.object(auth_sessions, "AUTH_SESSION_TTL_SECONDS", -10):
            token = auth_sessions.create_auth_session(1)
        self.assertIsNone(auth_sessions.get_user_id_for_token(token))

    def test_garbage_tokens_return_none(self):
        for token in ["", None, "nodots", ".", "...", "a.b", "!!!.???", "e30.e30"]:
            with self.subTest(token=token):
                self.assertIsNone(auth_sessions.get_user_id_for_token(token))

    def test_non_ascii_token_returns_none_instead_of_crashing(self):
        # Cookie values come from the client, so they can contain anything.
        self.assertIsNone(auth_sessions.get_user_id_for_token("abc.é"))

    def test_refuses_to_issue_tokens_without_a_secret(self):
        with patch.object(auth_sessions, "AUTH_SECRET_KEY", ""):
            with self.assertRaises(RuntimeError):
                auth_sessions.create_auth_session(1)

    def test_tokens_are_never_accepted_when_no_secret_is_configured(self):
        token = auth_sessions.create_auth_session(1)
        with patch.object(auth_sessions, "AUTH_SECRET_KEY", ""):
            self.assertIsNone(auth_sessions.get_user_id_for_token(token))

    def test_delete_session_is_a_harmless_no_op(self):
        self.assertIsNone(auth_sessions.delete_auth_session("anything"))


if __name__ == "__main__":
    unittest.main()
