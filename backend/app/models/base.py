from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, TypeDecorator
from sqlalchemy.orm import DeclarativeBase

from backend.app.core.time import to_utc


SCHEMA_VERSION = "module-3-v2"


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator[datetime]):
    """Persist aware datetimes in UTC and reject naïve values."""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_bind_param(
        self, value: datetime | None, dialect: Any
    ) -> datetime | None:
        return None if value is None else to_utc(value)

    def process_result_value(
        self, value: datetime | None, dialect: Any
    ) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=value.tzinfo or timezone.utc)
