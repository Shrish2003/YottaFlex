import unittest
from datetime import datetime, timedelta, timezone

from backend.app.core.time import now_utc, parse_utc, serialize_utc, to_utc


class TimeTests(unittest.TestCase):
    def test_now_is_timezone_aware_utc(self) -> None:
        value = now_utc()
        self.assertIsNotNone(value.tzinfo)
        self.assertEqual(value.utcoffset(), timedelta(0))

    def test_non_utc_value_is_converted(self) -> None:
        value = datetime(2026, 10, 27, 12, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        self.assertEqual(to_utc(value), datetime(2026, 10, 27, 6, 30, tzinfo=timezone.utc))

    def test_naive_datetime_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            to_utc(datetime(2026, 10, 27, 12, 0))

    def test_serialization_is_utc_iso8601(self) -> None:
        value = datetime(2026, 10, 27, 12, 0, 1, 123000, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        self.assertEqual(serialize_utc(value), "2026-10-27T06:30:01.123000Z")

    def test_parse_round_trip_preserves_instant(self) -> None:
        serialized = "2026-10-27T06:30:01.123000Z"
        self.assertEqual(serialize_utc(parse_utc(serialized)), serialized)

    def test_naive_timestamp_string_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_utc("2026-10-27T06:30:01")

    def test_invalid_timestamp_string_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_utc("not-a-timestamp")


if __name__ == "__main__":
    unittest.main()
