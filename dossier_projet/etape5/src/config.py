"""Environment configuration for the monitoring exporter."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceTarget:
    """A fixed application health endpoint to probe."""

    name: str
    url: str


@dataclass(frozen=True)
class Settings:
    """Validated runtime settings sourced from environment variables."""

    targets: tuple[ServiceTarget, ...]
    probe_interval_seconds: float = 15.0
    probe_timeout_seconds: float = 5.0
    background_probes: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        interval = _positive_float("PROBE_INTERVAL_SECONDS", 15.0)
        timeout = _positive_float("PROBE_TIMEOUT_SECONDS", 5.0)
        enabled = os.getenv("ENABLE_BACKGROUND_PROBES", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        return cls(
            targets=(
                ServiceTarget(
                    "data-api",
                    os.getenv("DATA_API_URL", "http://localhost:8000/health"),
                ),
                ServiceTarget(
                    "model-api",
                    os.getenv("MODEL_API_URL", "http://localhost:8001/health"),
                ),
                ServiceTarget(
                    "web-app",
                    os.getenv("WEB_APP_URL", "http://localhost:8080/health"),
                ),
            ),
            probe_interval_seconds=interval,
            probe_timeout_seconds=timeout,
            background_probes=enabled,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value
