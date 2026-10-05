"""
Centralized logging facility for Echo Weather.
Provides colored console formatting and clean logging.
"""

import logging
import os
import sys
from typing import Optional

COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[35m",
}
RESET = "\033[0m"


class ColoredFormatter(logging.Formatter):
    """Custom formatter providing ANSI colors for terminal output."""

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None, use_color: bool = True):
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.use_color = use_color and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        orig_levelname = record.levelname
        if self.use_color and orig_levelname in COLORS:
            record.levelname = f"{COLORS[orig_levelname]}{orig_levelname:<7}{RESET}"
        formatted = super().format(record)
        record.levelname = orig_levelname
        return formatted


_INITIALIZED = False


def setup_logging(level: Optional[int] = None) -> logging.Logger:
    """Configures the root 'echo_weather' logger."""
    global _INITIALIZED
    root_logger = logging.getLogger("echo_weather")

    if _INITIALIZED:
        if level is not None:
            root_logger.setLevel(level)
            for h in root_logger.handlers:
                h.setLevel(level)
        return root_logger

    if level is None:
        env_level = os.environ.get("ECHO_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, env_level, logging.INFO)

    root_logger.setLevel(level)
    root_logger.propagate = False

    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        fmt = "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
        datefmt = "%H:%M:%S"
        handler.setFormatter(ColoredFormatter(fmt=fmt, datefmt=datefmt))
        root_logger.addHandler(handler)

    _INITIALIZED = True
    return root_logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Returns a configured logger instance."""
    if not _INITIALIZED:
        setup_logging()

    if not name or name == "echo_weather":
        return logging.getLogger("echo_weather")

    if not name.startswith("echo_weather"):
        clean_name = name.replace(".py", "")
        if clean_name in ("__main__", "main"):
            clean_name = "main"
        name = f"echo_weather.{clean_name}"

    return logging.getLogger(name)


logger = get_logger("echo_weather")
