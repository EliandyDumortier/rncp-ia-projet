"""Small security helpers shared by the model API and its data loader."""

from __future__ import annotations

import re

_URL_CREDENTIALS = re.compile(r"(://[^:/\s]+:)([^@/\s]+)(@)")
_BEARER = re.compile(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+")
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(password|secret|token|authorization|database_url)\s*[=:]\s*([^\s,;]+)"
)


def redact_secrets(value: object) -> str:
    """Return an error message with common credential forms removed."""

    text = str(value)
    text = _URL_CREDENTIALS.sub(r"\1***\3", text)
    text = _BEARER.sub(r"\1***", text)
    return _SENSITIVE_ASSIGNMENT.sub(r"\1=***", text)


def safe_exception(exc: BaseException) -> str:
    """Keep an exception useful for diagnosis without exposing credentials."""

    return f"{type(exc).__name__}: {redact_secrets(exc)}"
