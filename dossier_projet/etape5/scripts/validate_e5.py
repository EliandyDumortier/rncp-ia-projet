#!/usr/bin/env python3
"""Run reproducible E5 checks and write private evidence under .validation/."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

ETAPE5_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = ETAPE5_DIR.parents[1]
ETAPE3_DIR = REPOSITORY_DIR / "dossier_projet/etape3"
OUTPUT_DIR = ETAPE5_DIR / ".validation"


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


def run_command(name: str, command: list[str], cwd: Path) -> Check:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Check(name, False, f"{type(exc).__name__}: command unavailable or timed out")
    output = (result.stdout + result.stderr).strip()
    summary = output[-1500:] if output else "command completed"
    return Check(name, result.returncode == 0, summary)


def check_json() -> Check:
    path = ETAPE5_DIR / "config/grafana/dashboards/kdrama-overview.json"
    try:
        dashboard = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Check("grafana-dashboard", False, f"{type(exc).__name__}: invalid JSON")
    panels = dashboard.get("panels", [])
    valid = dashboard.get("uid") == "kdrama-overview" and len(panels) >= 8
    return Check(
        "grafana-dashboard",
        valid,
        f"uid={dashboard.get('uid')}, panels={len(panels)}",
    )


def http_endpoint(
    name: str, url: str, expect_json: bool = True
) -> tuple[Check, object | None]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if expect_json else raw
            passed = 200 <= response.status < 300
            return Check(name, passed, f"HTTP {response.status}"), payload
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return Check(name, False, f"{type(exc).__name__}: endpoint unavailable"), None


def file_contains(name: str, relative: str, tokens: tuple[str, ...]) -> Check:
    path = ETAPE5_DIR / relative
    try:
        content = path.read_text(encoding="utf-8").lower()
    except OSError as exc:
        return Check(name, False, f"{type(exc).__name__}: missing file {relative}")
    missing = [token for token in tokens if token.lower() not in content]
    return Check(name, not missing, "complete" if not missing else f"missing: {missing}")


def build_checks(runtime: bool) -> tuple[list[Check], dict[str, object]]:
    etape3_python = (
        ETAPE3_DIR / ".venv/Scripts/python.exe"
        if sys.platform == "win32"
        else ETAPE3_DIR / ".venv/bin/python"
    )
    checks = [
        run_command(
            "pytest-etape5",
            [
                sys.executable,
                "-m",
                "pytest",
                "tests",
                "-q",
                "--cov=src",
                "--cov-report=term-missing",
                "--cov-fail-under=85",
            ],
            ETAPE5_DIR,
        ),
        run_command(
            "ruff-etape5",
            [sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"],
            ETAPE5_DIR,
        ),
        run_command(
            "pytest-incident-regression",
            [
                str(etape3_python),
                "-m",
                "pytest",
                "tests/test_data_loader.py::test_get_database_url_rejects_render_value_with_quotes",
                "tests/test_model_api.py::TestHealthEndpoint::test_health_returns_503_when_model_is_unavailable",
                "tests/test_security_utils.py",
                "-q",
            ],
            ETAPE3_DIR,
        ),
        run_command(
            "compose-config",
            ["docker", "compose", "-f", "docker-compose.monitoring.yml", "config", "--quiet"],
            ETAPE5_DIR,
        ),
        run_command(
            "prometheus-config",
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint",
                "/bin/promtool",
                "-v",
                f"{ETAPE5_DIR / 'config/prometheus'}:/etc/prometheus:ro",
                "prom/prometheus:v2.54.1",
                "check",
                "config",
                "/etc/prometheus/prometheus.yml",
            ],
            REPOSITORY_DIR,
        ),
        run_command(
            "alertmanager-config",
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint",
                "/bin/amtool",
                "-v",
                f"{ETAPE5_DIR / 'config/alertmanager'}:/etc/alertmanager:ro",
                "prom/alertmanager:v0.27.0",
                "check-config",
                "/etc/alertmanager/alertmanager.yml",
            ],
            REPOSITORY_DIR,
        ),
        check_json(),
        file_contains(
            "metrics-thresholds-doc",
            "docs/specification_monitoring.md",
            ("métriques, risques et seuils", "kdrama_service_up", "0,25"),
        ),
        file_contains(
            "installation-doc",
            "README.md",
            ("installation", "docker compose", "prometheus", "grafana"),
        ),
        file_contains(
            "incident-doc",
            "docs/rapport_incident.md",
            ("cause racine", "reproduction", "résolution implémentée", "versionnement"),
        ),
        run_command(
            "validation-output-ignored",
            ["git", "check-ignore", "-q", "dossier_projet/etape5/.validation/report.json"],
            REPOSITORY_DIR,
        ),
    ]

    runtime_data: dict[str, object] = {}
    if runtime:
        endpoints = {
            "runtime-exporter": ("http://localhost:9101/health", True),
            "runtime-prometheus": ("http://localhost:9090/-/ready", False),
            "runtime-grafana": ("http://localhost:3000/api/health", True),
            "runtime-alertmanager": ("http://localhost:9093/-/ready", False),
            "runtime-mailpit": ("http://localhost:8025/api/v1/info", True),
            "runtime-targets": ("http://localhost:9101/targets", True),
            "runtime-alert-events": ("http://localhost:9101/alerts", True),
        }
        for name, (url, expect_json) in endpoints.items():
            check, payload = http_endpoint(name, url, expect_json)
            checks.append(check)
            runtime_data[name] = payload

        targets = runtime_data.get("runtime-targets")
        target_values = targets.get("targets", []) if isinstance(targets, dict) else []
        all_healthy = len(target_values) == 3 and all(
            target.get("healthy") is True
            for target in target_values
            if isinstance(target, dict)
        )
        checks.append(Check("three-services-healthy", all_healthy, f"targets={len(target_values)}"))

        mailpit = runtime_data.get("runtime-mailpit")
        alerts = runtime_data.get("runtime-alert-events")
        message_count = mailpit.get("Messages", 0) if isinstance(mailpit, dict) else 0
        alert_values = alerts.get("alerts", []) if isinstance(alerts, dict) else []
        alert_demo = message_count > 0 and any(
            alert.get("status") in {"firing", "resolved"}
            for alert in alert_values
            if isinstance(alert, dict)
        )
        checks.append(
            Check(
                "alert-notification-demonstrated",
                alert_demo,
                f"mailpit_messages={message_count}, webhook_events={len(alert_values)}",
            )
        )
    return checks, runtime_data


def criteria_status(checks: list[Check], runtime: bool) -> dict[str, str]:
    passed = {check.name for check in checks if check.passed}
    configured = {
        "compose-config",
        "prometheus-config",
        "alertmanager-config",
        "grafana-dashboard",
    }.issubset(passed)
    return {
        "C20.1": "PASS" if "metrics-thresholds-doc" in passed else "FAIL",
        "C20.2": "MANUAL_REVIEW",
        "C20.3": "PASS" if runtime and "three-services-healthy" in passed else "CONFIGURED",
        "C20.4": "PASS" if "pytest-etape5" in passed else "FAIL",
        "C20.5": (
            "PASS"
            if runtime and "alert-notification-demonstrated" in passed
            else "CONFIGURED" if configured else "FAIL"
        ),
        "C20.6": "PASS" if "installation-doc" in passed else "FAIL",
        "C20.7": "MANUAL_REVIEW",
        "C21.1": "MANUAL_REVIEW",
        "C21.2": (
            "PASS"
            if {"incident-doc", "pytest-incident-regression"}.issubset(passed)
            else "FAIL"
        ),
        "C21.3": "MANUAL_REVIEW",
        "C21.4": "MANUAL_REVIEW",
        "C21.5": "LOCAL_COMMITS_PR_REQUIRED",
    }


def write_report(checks: list[Check], criteria: dict[str, str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    report = {
        "generated_at": timestamp,
        "automated_checks_passed": all(check.passed for check in checks),
        "checks": [asdict(check) for check in checks],
        "criteria": criteria,
    }
    (OUTPUT_DIR / "validation-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Rapport de validation local E5",
        "",
        f"Généré le : {timestamp}",
        "",
        "## Contrôles automatisés",
        "",
    ]
    lines.extend(
        f"- {'PASS' if check.passed else 'FAIL'} — {check.name}: {check.detail.splitlines()[-1]}"
        for check in checks
    )
    lines.extend(["", "## Critères RNCP", ""])
    lines.extend(f"- {criterion}: {status}" for criterion, status in criteria.items())
    (OUTPUT_DIR / "validation-report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime",
        action="store_true",
        help="also check the running local monitoring stack and alert evidence",
    )
    args = parser.parse_args()
    checks, _ = build_checks(args.runtime)
    criteria = criteria_status(checks, args.runtime)
    write_report(checks, criteria)

    for check in checks:
        print(f"{'PASS' if check.passed else 'FAIL':4}  {check.name}: {check.detail.splitlines()[-1]}")
    print("\nRNCP criteria status:")
    for criterion, status in criteria.items():
        print(f"{criterion}: {status}")
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
