import unittest
from unittest.mock import patch

from src.config import settings


class NormalizeDatabaseUrlTests(unittest.TestCase):
    def test_adds_sslmode_when_there_is_no_query_string(self):
        self.assertEqual(
            settings.normalize_database_url("postgresql://u:p@host:5432/db"),
            "postgresql://u:p@host:5432/db?sslmode=require",
        )

    def test_appends_to_an_existing_query_string(self):
        self.assertEqual(
            settings.normalize_database_url("postgresql://u:p@host/db?application_name=x"),
            "postgresql://u:p@host/db?application_name=x&sslmode=require",
        )

    def test_leaves_an_explicit_sslmode_alone(self):
        url = "postgresql://u:p@postgres:5432/db?sslmode=disable"
        self.assertEqual(settings.normalize_database_url(url), url)


class RequiredSettingTests(unittest.TestCase):
    def test_missing_database_url_raises_a_helpful_error(self):
        with patch.object(settings, "DATABASE_URL", None):
            with self.assertRaises(ValueError) as ctx:
                settings.get_database_url()
        self.assertIn("DATABASE_URL", str(ctx.exception))

    def test_empty_database_url_counts_as_missing(self):
        with patch.object(settings, "DATABASE_URL", ""):
            with self.assertRaises(ValueError):
                settings.get_database_url()

    def test_database_url_is_normalized_when_present(self):
        with patch.object(settings, "DATABASE_URL", "postgresql://u:p@host/db"):
            self.assertTrue(settings.get_database_url().endswith("sslmode=require"))

    def test_missing_groq_key_raises_a_helpful_error(self):
        with patch.object(settings, "GROQ_API_KEY", None):
            with self.assertRaises(ValueError) as ctx:
                settings.get_groq_api_key()
        self.assertIn("GROQ_API_KEY", str(ctx.exception))

    def test_groq_key_is_returned_when_present(self):
        with patch.object(settings, "GROQ_API_KEY", "gsk_test"):
            self.assertEqual(settings.get_groq_api_key(), "gsk_test")


if __name__ == "__main__":
    unittest.main()
