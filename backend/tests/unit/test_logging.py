import io
import logging
import unittest

from backend.app.core.logging import setup_logging


class LoggingTests(unittest.TestCase):
    def tearDown(self) -> None:
        logger = logging.getLogger("yottaflex.test")
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)

    def test_setup_is_idempotent_and_configures_level(self) -> None:
        stream = io.StringIO()
        logger = setup_logging("debug", logger_name="yottaflex.test", stream=stream)
        setup_logging("WARNING", logger_name="yottaflex.test", stream=stream)
        self.assertEqual(logger.level, logging.WARNING)
        self.assertEqual(len(logger.handlers), 1)

    def test_log_message_is_written_without_secret_values_from_setup(self) -> None:
        stream = io.StringIO()
        logger = setup_logging(logger_name="yottaflex.test", stream=stream)
        logger.info("foundation initialized")
        self.assertIn("foundation initialized", stream.getvalue())

    def test_invalid_level_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            setup_logging("TRACE", logger_name="yottaflex.test")

    def test_empty_logger_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            setup_logging(logger_name=" ")


if __name__ == "__main__":
    unittest.main()
