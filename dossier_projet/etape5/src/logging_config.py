"""Structured logging helpers with defensive secret redaction."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "database_url",
    "jwt",
    "jwt_secret",
    "password",
    "secret",
    "token",
}

_URL_CREDENTIALS = re.compile(r"(://[^:/\s]+:)([^@/\s]+)(@)")
_BEARER = re.compile(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+")
_KEY_VALUE = re.compile(
    r"(?i)\b(password|secret|token|authorization|database_url)\s*[=:]\s*([^\s,;]+)"
)


def redact_text(value: str) -> str:
    """Remove common credential forms without logging their original value."""

    value = _URL_CREDENTIALS.sub(r"\1***\3", value)
    value = _BEARER.sub(r"\1***", value)
    return _KEY_VALUE.sub(r"\1=***", value)


def sanitize(value: Any) -> Any:
    """Recursively redact sensitive keys and strings from structured events."""

    if isinstance(value, dict):
        return {
            str(key): "***" if str(key).lower() in SENSITIVE_KEYS else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


class JsonFormatter(logging.Formatter):
    """Emit compact machine-readable logs with an allow-listed context."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_text(record.getMessage()),
        }
        event_data = getattr(record, "event_data", None)
        if isinstance(event_data, dict):
            payload["context"] = sanitize(event_data)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once for container and local execution."""

    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, level, logging.INFO))
