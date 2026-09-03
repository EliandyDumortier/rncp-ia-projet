from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from security_utils import redact_secrets, safe_exception  # noqa: E402


def test_redact_database_password_and_token() -> None:
    message = (
        "cannot parse postgresql://user:very-secret@db/kdrama "
        "authorization=Bearer-token"
    )
    redacted = redact_secrets(message)
    assert "very-secret" not in redacted
    assert "Bearer-token" not in redacted
    assert redacted.count("***") == 2


def test_safe_exception_keeps_type_but_not_password() -> None:
    result = safe_exception(ValueError("password=do-not-log"))
    assert result.startswith("ValueError:")
    assert "do-not-log" not in result
