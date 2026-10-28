"""Timezone-aware UTC helpers."""

from __future__ import annotations

from datetime import datetime, timezone


UTC = timezone.utc


def now_utc() -> datetime:
    """Return the current timezone-aware UTC datetime."""

    return datetime.now(UTC)


def require_aware(value: datetime) -> datetime:
    """Return an aware datetime or reject a naïve datetime."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value


def to_utc(value: datetime) -> datetime:
    """Convert an aware datetime to UTC."""

    return require_aware(value).astimezone(UTC)


def serialize_utc(value: datetime) -> str:
    """Serialize an aware datetime as an ISO 8601 UTC value."""

    return to_utc(value).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    """Parse an ISO 8601 timestamp and return an aware UTC datetime."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be a non-empty string")
    normalized = value.strip()
    if normalized.endswith(("Z", "z")):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid ISO 8601 timestamp: {value!r}") from exc
    return to_utc(parsed)


def duration_minutes(start: datetime, end: datetime) -> int:
    """Return elapsed whole minutes between two aware timestamps."""

    return int((to_utc(end) - to_utc(start)).total_seconds() // 60)
