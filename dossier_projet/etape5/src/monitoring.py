"""Health probes and bounded-cardinality Prometheus metrics."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any

import httpx
from prometheus_client import CollectorRegistry, Counter, Gauge

from .config import ServiceTarget, Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProbeResult:
    """Normalized result of a single service health probe."""

    service: str
    up: bool
    healthy: bool
    status_code: int
    latency_seconds: float
    reason: str
    model_loaded: bool | None = None
    model_trained: bool | None = None

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


class ApplicationMonitor:
    """Probe the application services and expose their operational state."""

    def __init__(
        self,
        settings: Settings,
        registry: CollectorRegistry | None = None,
    ) -> None:
        self.settings = settings
        self.registry = registry or CollectorRegistry()
        self.results: dict[str, ProbeResult] = {}
        self.failures = {target.name: 0 for target in settings.targets}

        self.service_up = Gauge(
            "kdrama_service_up",
            "1 when the service health endpoint is reachable.",
            ["service"],
            registry=self.registry,
        )
        self.service_healthy = Gauge(
            "kdrama_service_healthy",
            "1 when the service reports a healthy functional state.",
            ["service"],
            registry=self.registry,
        )
        self.probe_latency = Gauge(
            "kdrama_service_probe_latency_seconds",
            "Duration of the latest application health probe.",
            ["service"],
            registry=self.registry,
        )
        self.http_status = Gauge(
            "kdrama_service_http_status_code",
            "HTTP status returned by the latest health probe, or zero.",
            ["service"],
            registry=self.registry,
        )
        self.consecutive_failures = Gauge(
            "kdrama_service_consecutive_failures",
            "Number of consecutive unhealthy probes.",
            ["service"],
            registry=self.registry,
        )
        self.last_success = Gauge(
            "kdrama_service_last_success_timestamp_seconds",
            "Unix timestamp of the latest healthy probe.",
            ["service"],
            registry=self.registry,
        )
        self.probe_total = Counter(
            "kdrama_service_probes_total",
            "Number of health probes by normalized outcome.",
            ["service", "reason"],
            registry=self.registry,
        )
        self.model_loaded = Gauge(
            "kdrama_observed_model_loaded",
            "Model loaded state observed from the model API health response.",
            registry=self.registry,
        )
        self.model_trained = Gauge(
            "kdrama_observed_model_trained",
            "Model trained state observed from the model API health response.",
            registry=self.registry,
        )

    async def probe(self, target: ServiceTarget, client: httpx.AsyncClient) -> ProbeResult:
        started = time.perf_counter()
        try:
            response = await client.get(target.url)
            latency = time.perf_counter() - started
        except httpx.TimeoutException:
            return self._record(target.name, False, False, 0, 0.0, "timeout")
        except httpx.HTTPError:
            return self._record(target.name, False, False, 0, 0.0, "network")

        if response.status_code != 200:
            return self._record(
                target.name,
                True,
                False,
                response.status_code,
                latency,
                "http",
            )

        try:
            payload = response.json()
        except ValueError:
            return self._record(
                target.name,
                True,
                False,
                response.status_code,
                latency,
                "invalid_json",
            )

        healthy = _payload_is_healthy(payload)
        reason = "ok" if healthy else "degraded"
        loaded = _optional_bool(payload, "model_loaded")
        trained = _optional_bool(payload, "model_trained")
        return self._record(
            target.name,
            True,
            healthy,
            response.status_code,
            latency,
            reason,
            loaded,
            trained,
        )

    def _record(
        self,
        service: str,
        up: bool,
        healthy: bool,
        status_code: int,
        latency: float,
        reason: str,
        model_loaded: bool | None = None,
        model_trained: bool | None = None,
    ) -> ProbeResult:
        result = ProbeResult(
            service=service,
            up=up,
            healthy=healthy,
            status_code=status_code,
            latency_seconds=round(latency, 6),
            reason=reason,
            model_loaded=model_loaded,
            model_trained=model_trained,
        )
        self.results[service] = result
        self.failures[service] = 0 if healthy else self.failures[service] + 1
        self.service_up.labels(service).set(int(up))
        self.service_healthy.labels(service).set(int(healthy))
        self.probe_latency.labels(service).set(latency)
        self.http_status.labels(service).set(status_code)
        self.consecutive_failures.labels(service).set(self.failures[service])
        self.probe_total.labels(service, reason).inc()
        if healthy:
            self.last_success.labels(service).set_to_current_time()
        if service == "model-api":
            if model_loaded is not None:
                self.model_loaded.set(int(model_loaded))
            if model_trained is not None:
                self.model_trained.set(int(model_trained))

        log_method = logger.info if healthy else logger.warning
        log_method(
            "service_probe",
            extra={
                "event_data": {
                    "service": service,
                    "healthy": healthy,
                    "status_code": status_code,
                    "latency_seconds": result.latency_seconds,
                    "reason": reason,
                }
            },
        )
        return result

    async def run_once(self, client: httpx.AsyncClient | None = None) -> list[ProbeResult]:
        if client is not None:
            return await asyncio.gather(
                *(self.probe(target, client) for target in self.settings.targets)
            )
        async with httpx.AsyncClient(timeout=self.settings.probe_timeout_seconds) as owned:
            return await asyncio.gather(
                *(self.probe(target, owned) for target in self.settings.targets)
            )

    async def run_forever(self) -> None:
        while True:
            await self.run_once()
            await asyncio.sleep(self.settings.probe_interval_seconds)


def _payload_is_healthy(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    status = str(payload.get("status", "")).lower()
    if status not in {"ok", "healthy"}:
        return False
    if payload.get("database") == "error":
        return False
    if "model_loaded" in payload and payload.get("model_loaded") is not True:
        return False
    if "model_trained" in payload and payload.get("model_trained") is not True:
        return False
    return True


def _optional_bool(payload: Any, key: str) -> bool | None:
    if isinstance(payload, dict) and key in payload:
        return payload[key] is True
    return None
