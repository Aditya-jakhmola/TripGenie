import unittest
from unittest.mock import patch

from src.auth import passwords


class PasswordHashingTests(unittest.TestCase):
    def setUp(self):
        # A low iteration count keeps the suite fast. The stored hash records
        # its own iteration count, so verification is unaffected.
        patcher = patch.object(passwords, "PASSWORD_HASH_ITERATIONS", 1000)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_correct_password_verifies(self):
        stored = passwords.hash_password("correct horse battery staple")
        self.assertTrue(passwords.verify_password("correct horse battery staple", stored))

    def test_wrong_password_is_rejected(self):
        stored = passwords.hash_password("correct horse battery staple")
        self.assertFalse(passwords.verify_password("wrong password", stored))

    def test_password_is_case_sensitive(self):
        stored = passwords.hash_password("Secret123")
        self.assertFalse(passwords.verify_password("secret123", stored))

    def test_same_password_hashes_differently_each_time(self):
        # Different random salts mean identical passwords never share a hash.
        self.assertNotEqual(
            passwords.hash_password("same-password"),
            passwords.hash_password("same-password"),
        )

    def test_stored_format_is_iterations_salt_digest(self):
        iterations, salt, digest = passwords.hash_password("pw").split("$")
        self.assertEqual(iterations, "1000")
        self.assertEqual(len(salt), 32)      # 16 random bytes, hex encoded
        self.assertEqual(len(digest), 64)    # SHA-256, hex encoded

    def test_plaintext_is_not_stored(self):
        self.assertNotIn("my-plain-password", passwords.hash_password("my-plain-password"))

    def test_unicode_password_round_trips(self):
        stored = passwords.hash_password("pässwörd-密码-🔑")
        self.assertTrue(passwords.verify_password("pässwörd-密码-🔑", stored))

    def test_empty_password_round_trips_but_does_not_match_others(self):
        stored = passwords.hash_password("")
        self.assertTrue(passwords.verify_password("", stored))
        self.assertFalse(passwords.verify_password("x", stored))

    def test_stored_iteration_count_is_honoured_after_a_config_change(self):
        stored = passwords.hash_password("pw")
        with patch.object(passwords, "PASSWORD_HASH_ITERATIONS", 5000):
            self.assertTrue(passwords.verify_password("pw", stored))

    def test_malformed_stored_values_are_rejected_not_raised(self):
        for stored in ["", "garbage", "a$b", "1$2$3$4", "abc$def$ghi", "1000$abcd$é", None]:
            with self.subTest(stored=stored):
                self.assertFalse(passwords.verify_password("pw", stored))

    def test_corrupt_salt_is_rejected_not_raised(self):
        self.assertFalse(passwords.verify_password("pw", "1000$not-hex$abcd"))

    def test_zero_iterations_is_rejected_not_raised(self):
        self.assertFalse(passwords.verify_password("pw", "0$abcd$abcd"))


if __name__ == "__main__":
    unittest.main()
