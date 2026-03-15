"""
Axora Logger - rotating file logger with console output
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_loggers = {}


def get_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # Console handler (WARNING+ only, clean format)
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        ch.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(ch)

        # File handler (DEBUG+, rotating)
        _log_file = log_file or os.environ.get("AXORA_LOG_FILE", "logs/axora.log")
        Path(_log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            _log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(fh)

    _loggers[name] = logger
    return logger
