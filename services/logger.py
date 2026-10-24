"""Process-wide logging setup."""

from __future__ import annotations

import logging
import sys


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("aura")
    if logger.handlers:
        return logger
    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[AURA] %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


log = setup_logging()
