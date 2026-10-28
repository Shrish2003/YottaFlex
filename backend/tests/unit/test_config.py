import os
import unittest
from unittest.mock import patch

from backend.app.core.config import ConfigurationError, Settings


class SettingsTests(unittest.TestCase):
    def test_defaults_are_technical_only(self) -> None:
        settings = Settings()
        self.assertEqual(settings.app_env, "development")
        self.assertEqual(settings.log_level, "INFO")

    def test_environment_values_override_defaults(self) -> None:
        settings = Settings.from_env(
            {
                "YOTTAFLEX_APP_ENV": "test",
                "YOTTAFLEX_LOG_LEVEL": "debug",
                "YOTTAFLEX_DATABASE_URL": "sqlite:///test.sqlite",
            }
        )
        self.assertEqual(settings.app_env, "test")
        self.assertEqual(settings.log_level, "DEBUG")
        self.assertEqual(settings.database_url, "sqlite:///test.sqlite")

    def test_database_url_takes_precedence_over_legacy_name(self) -> None:
        settings = Settings.from_env(
            {
                "DATABASE_URL": "postgresql+psycopg2://localhost/cold_chain_dev",
                "YOTTAFLEX_DATABASE_URL": "sqlite:///legacy.sqlite",
            }
        )
        self.assertEqual(
            settings.database_url,
            "postgresql+psycopg2://localhost/cold_chain_dev",
        )

    def test_process_environment_can_be_loaded(self) -> None:
        with patch.dict(
            os.environ,
            {"YOTTAFLEX_APP_ENV": "ci", "YOTTAFLEX_LOG_LEVEL": "warning"},
            clear=False,
        ):
            settings = Settings.from_env()
        self.assertEqual(settings.app_env, "ci")
        self.assertEqual(settings.log_level, "WARNING")

    def test_empty_environment_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError):
            Settings(app_env="   ")

    def test_invalid_log_level_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError):
            Settings(log_level="TRACE")

    def test_explicit_invalid_values_are_not_replaced(self) -> None:
        with self.assertRaises(ConfigurationError):
            Settings.from_env({"YOTTAFLEX_LOG_LEVEL": "not-a-level"})

    def test_empty_database_url_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError):
            Settings.from_env({"YOTTAFLEX_DATABASE_URL": " "})

    def test_build_app_missing_database_url_raises_helpful_runtime_error(self) -> None:
        from backend.app.main import build_app

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                build_app()
            self.assertIn("DATABASE_URL or YOTTAFLEX_DATABASE_URL", str(ctx.exception))

    def test_build_app_succeeds_with_configured_database_url(self) -> None:
        from backend.app.main import build_app

        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}):
            app = build_app()
            self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
