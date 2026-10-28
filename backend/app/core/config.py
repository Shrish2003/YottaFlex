"""Minimal environment-backed technical configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from collections.abc import Mapping


class ConfigurationError(ValueError):
    """Raised when technical configuration is invalid."""


@dataclass(frozen=True)
class Settings:
    """Technical settings only; business settings belong to later modules."""

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str | None = None

    def __post_init__(self) -> None:
        app_env = self.app_env.strip().lower()
        log_level = self.log_level.strip().upper()
        if not app_env:
            raise ConfigurationError("app_env must not be empty")
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError(f"unsupported log_level: {self.log_level!r}")
        if self.database_url is not None and not self.database_url.strip():
            raise ConfigurationError("database_url must not be empty")
        object.__setattr__(self, "app_env", app_env)
        object.__setattr__(self, "log_level", log_level)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        values = os.environ if environ is None else environ
        return cls(
            app_env=values.get("YOTTAFLEX_APP_ENV", cls.app_env),
            log_level=values.get("YOTTAFLEX_LOG_LEVEL", cls.log_level),
            database_url=values.get(
                "DATABASE_URL", values.get("YOTTAFLEX_DATABASE_URL")
            ),
        )
