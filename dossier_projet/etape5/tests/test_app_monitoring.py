from __future__ import annotations

from fastapi.testclient import TestClient

from src.app_monitoring import create_app
from src.config import ServiceTarget, Settings


def test_health_metrics_and_alert_webhook() -> None:
    settings = Settings(
        targets=(ServiceTarget("data-api", "http://unused/health"),),
        background_probes=False,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "kdrama_alertmanager_notifications_total" in metrics.text

        response = client.post(
            "/alerts/webhook",
            json={
                "alerts": [
                    {
                        "status": "firing",
                        "labels": {
                            "alertname": "KDramaServiceDown",
                            "severity": "critical",
                            "service": "model-api",
                            "password": "must-not-pass",
                        },
                        "annotations": {
                            "summary": "Model API unavailable",
                            "token": "must-not-pass",
                        },
                    }
                ]
            },
        )
        alerts = client.get("/alerts").json()["alerts"]

    assert response.json() == {"accepted": 1}
    assert alerts[0]["labels"] == {
        "alertname": "KDramaServiceDown",
        "severity": "critical",
        "service": "model-api",
    }
    assert "must-not-pass" not in str(alerts)
