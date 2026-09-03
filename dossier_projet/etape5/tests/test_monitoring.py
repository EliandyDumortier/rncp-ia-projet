from __future__ import annotations

import json
import logging

import httpx
import pytest
from prometheus_client import CollectorRegistry, generate_latest

from src.config import ServiceTarget, Settings
from src.logging_config import JsonFormatter, sanitize
from src.monitoring import ApplicationMonitor


def settings_for(target: ServiceTarget) -> Settings:
    return Settings(
        targets=(target,),
        probe_interval_seconds=1,
        probe_timeout_seconds=1,
        background_probes=False,
    )


@pytest.mark.asyncio
async def test_healthy_model_probe_exports_metrics() -> None:
    target = ServiceTarget("model-api", "https://model.test/health")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "healthy", "model_loaded": True, "model_trained": True},
        )

    registry = CollectorRegistry()
    monitor = ApplicationMonitor(settings_for(target), registry)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await monitor.probe(target, client)

    assert result.healthy is True
    assert result.model_trained is True
    metrics = generate_latest(registry).decode()
    assert 'kdrama_service_healthy{service="model-api"} 1.0' in metrics
    assert "kdrama_observed_model_trained 1.0" in metrics


@pytest.mark.asyncio
async def test_degraded_payload_counts_consecutive_failures() -> None:
    target = ServiceTarget("data-api", "https://data.test/health")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "degraded", "database": "error"})

    monitor = ApplicationMonitor(settings_for(target))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        first = await monitor.probe(target, client)
        await monitor.probe(target, client)

    assert first.up is True
    assert first.healthy is False
    assert first.reason == "degraded"
    assert monitor.failures["data-api"] == 2


@pytest.mark.asyncio
async def test_timeout_is_normalized_without_leaking_url() -> None:
    target = ServiceTarget("web-app", "https://user:secret@example.test/health")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("password=never-log", request=request)

    monitor = ApplicationMonitor(settings_for(target))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await monitor.probe(target, client)

    assert result.reason == "timeout"
    assert result.status_code == 0
    assert "secret" not in str(result)


def test_structured_logs_redact_credentials() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        "test",
        logging.ERROR,
        __file__,
        1,
        "connection failed: postgresql://user:supersecret@db/kdrama token=abc123",
        (),
        None,
    )
    parsed = json.loads(formatter.format(record))

    assert "supersecret" not in parsed["message"]
    assert "abc123" not in parsed["message"]
    assert "***" in parsed["message"]


def test_recursive_sanitization() -> None:
    cleaned = sanitize(
        {"password": "bad", "nested": {"authorization": "Bearer abc", "ok": 1}}
    )
    assert cleaned == {"password": "***", "nested": {"authorization": "***", "ok": 1}}
