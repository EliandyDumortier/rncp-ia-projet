"""FastAPI monitoring exporter and Alertmanager webhook receiver."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from .config import Settings
from .logging_config import configure_logging, sanitize
from .monitoring import ApplicationMonitor


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings.from_env()
    configure_logging(runtime_settings.log_level)
    logger = logging.getLogger(__name__)
    monitor = ApplicationMonitor(runtime_settings)
    alert_events: deque[dict[str, Any]] = deque(maxlen=100)
    alerts_received = Counter(
        "kdrama_alertmanager_notifications_total",
        "Number of Alertmanager webhook notifications received.",
        ["status"],
        registry=monitor.registry,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        task: asyncio.Task[None] | None = None
        if runtime_settings.background_probes:
            task = asyncio.create_task(monitor.run_forever())
        yield
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(
        title="K-Drama Application Monitoring",
        version="5.0.0",
        lifespan=lifespan,
    )
    app.state.monitor = monitor
    app.state.alert_events = alert_events

    @app.get("/health", tags=["monitoring"])
    async def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "healthy",
                "version": "5.0.0",
                "targets_configured": len(runtime_settings.targets),
            }
        )

    @app.get("/targets", tags=["monitoring"])
    async def targets() -> dict[str, Any]:
        return {
            "targets": [result.public_dict() for result in monitor.results.values()]
        }

    @app.post("/probe", tags=["monitoring"])
    async def probe_now() -> dict[str, Any]:
        results = await monitor.run_once()
        return {"targets": [result.public_dict() for result in results]}

    @app.get("/metrics", tags=["monitoring"])
    async def metrics() -> Response:
        return Response(generate_latest(monitor.registry), media_type=CONTENT_TYPE_LATEST)

    @app.post("/alerts/webhook", tags=["alerting"])
    async def alertmanager_webhook(request: Request) -> dict[str, int]:
        payload = await request.json()
        raw_alerts = payload.get("alerts", []) if isinstance(payload, dict) else []
        accepted = 0
        for raw_alert in raw_alerts[:50]:
            if not isinstance(raw_alert, dict):
                continue
            labels = raw_alert.get("labels", {})
            annotations = raw_alert.get("annotations", {})
            event = sanitize(
                {
                    "status": raw_alert.get("status", "unknown"),
                    "labels": {
                        key: labels.get(key)
                        for key in ("alertname", "severity", "service")
                        if isinstance(labels, dict) and labels.get(key) is not None
                    },
                    "annotations": {
                        key: annotations.get(key)
                        for key in ("summary", "description")
                        if isinstance(annotations, dict)
                        and annotations.get(key) is not None
                    },
                }
            )
            alert_events.append(event)
            normalized_status = (
                "firing" if event.get("status") == "firing" else "resolved"
            )
            alerts_received.labels(normalized_status).inc()
            logger.warning("alertmanager_event", extra={"event_data": event})
            accepted += 1
        return {"accepted": accepted}

    @app.get("/alerts", tags=["alerting"])
    async def recent_alerts() -> dict[str, Any]:
        return {"alerts": list(alert_events)}

    return app


app = create_app()
