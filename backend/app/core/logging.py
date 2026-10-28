"""Standard-library logging setup for the application foundation."""

from __future__ import annotations

import logging as stdlib_logging
from typing import TextIO


_LEVELS = {
    "DEBUG": stdlib_logging.DEBUG,
    "INFO": stdlib_logging.INFO,
    "WARNING": stdlib_logging.WARNING,
    "ERROR": stdlib_logging.ERROR,
    "CRITICAL": stdlib_logging.CRITICAL,
}
_HANDLER_MARKER = "_yottaflex_handler"


def setup_logging(
    level: str = "INFO",
    *,
    logger_name: str = "yottaflex",
    stream: TextIO | None = None,
) -> stdlib_logging.Logger:
    """Configure one idempotent stream handler for a named logger."""

    normalized_level = level.strip().upper()
    if normalized_level not in _LEVELS:
        raise ValueError(f"unsupported log level: {level!r}")
    if not logger_name.strip():
        raise ValueError("logger_name must not be empty")

    logger = stdlib_logging.getLogger(logger_name)
    logger.setLevel(_LEVELS[normalized_level])
    logger.propagate = False

    handler = next(
        (
            candidate
            for candidate in logger.handlers
            if getattr(candidate, _HANDLER_MARKER, False)
        ),
        None,
    )
    if handler is None:
        handler = stdlib_logging.StreamHandler(stream)
        setattr(handler, _HANDLER_MARKER, True)
        logger.addHandler(handler)
    elif stream is not None:
        handler.setStream(stream)

    handler.setLevel(_LEVELS[normalized_level])
    handler.setFormatter(
        stdlib_logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    return logger
