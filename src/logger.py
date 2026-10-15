import logging
import re
import sys
from pathlib import Path
from typing import Optional

from src.config import LOG_FILE


class SensitiveDataRedactor(logging.Filter):
    """Filter that scrubs PII and credentials from log messages and arguments (CWE-532)."""

    PATTERNS = [
        (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "[REDACTED_CARD]"),
        (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
        (re.compile(r"(?i)\b(password|secret|token|api[_-]?key)\s*[:=]\s*\S+"), r"\1=[REDACTED_SECRET]"),
        (re.compile(r"(?i)\b(bearer)\s+[a-zA-Z0-9_\-\.]+"), r"\1 [REDACTED_TOKEN]"),
    ]

    def _sanitize(self, text: str) -> str:
        for pattern, repl in self.PATTERNS:
            text = pattern.sub(repl, text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._sanitize(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._sanitize(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(self._sanitize(a) if isinstance(a, str) else a for a in record.args)
        return True


def setup_logger(
    name: str = "etl_pipeline",
    log_file: Optional[Path] = None,
    level: int = logging.INFO
) -> logging.Logger:
    """Configures and returns a singleton-like logger with file and console handlers."""
    target_log_file = log_file or LOG_FILE
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding duplicate handlers on multiple calls
    if logger.handlers:
        return logger

    # Attach sensitive data redactor
    logger.addFilter(SensitiveDataRedactor())

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | [%(name)s:%(funcName)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (persists to pipeline.log with utf-8 encoding)
    file_handler = logging.FileHandler(target_log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
