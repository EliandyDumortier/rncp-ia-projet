# ============================================================
# Monitoring du modèle d'IA — Collecte de métriques Prometheus
# Fichier : model_monitoring.py
#
# Métriques collectées :
#   1. Latence des requêtes (histogramme)
#   2. Nombre de requêtes par endpoint (compteur)
#   3. Drift de prédiction (jauge) — écart entre la distribution
#      des prédictions actuelles et de référence
#   4. Taux d'erreur (compteur + ratio)
#   5. Distribution des scores de recommandation (histogramme)
#   6. Utilisation du modèle (jauge : entraîné / non entraîné)
#
# Auteur : Équipe MLOps
# Étape 3 — RNCP AI Project
# ============================================================

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)

logger = logging.getLogger(__name__)

# ============================================================
# Registre Prometheus personnalisé
# ============================================================

# Utilisation d'un registre dédié pour éviter les conflits
# avec d'autres bibliothèques instrumentées.
REGISTRY = CollectorRegistry()


# ============================================================
# Définition des métriques Prometheus
# ============================================================

# --- Compteurs ---
REQUEST_COUNT = Counter(
    "kdrama_api_requests_total",
    "Nombre total de requêtes traitées par l'API.",
    labelnames=["endpoint", "method", "status"],
    registry=REGISTRY,
)

ERROR_COUNT = Counter(
    "kdrama_api_errors_total",
    "Nombre total d'erreurs rencontrées par l'API.",
    labelnames=["endpoint", "error_type"],
    registry=REGISTRY,
)

PREDICTION_COUNT = Counter(
    "kdrama_model_predictions_total",
    "Nombre total de prédictions générées par le modèle.",
    labelnames=["model_type", "mode"],
    registry=REGISTRY,
)

# --- Histogrammes ---
REQUEST_LATENCY = Histogram(
    "kdrama_api_request_latency_seconds",
    "Latence des requêtes API en secondes.",
    labelnames=["endpoint"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.075,
        0.1,
        0.25,
        0.5,
        0.75,
        1.0,
        2.5,
        5.0,
        7.5,
        10.0,
    ),
    registry=REGISTRY,
)

PREDICTION_SCORE_DISTRIBUTION = Histogram(
    "kdrama_model_prediction_score_distribution",
    "Distribution des scores de recommandation générés.",
    labelnames=["model_type"],
    buckets=(0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0),
    registry=REGISTRY,
)

MODEL_INFERENCE_TIME = Histogram(
    "kdrama_model_inference_time_seconds",
    "Temps d'inférence du modèle en secondes.",
    labelnames=["operation"],
    buckets=(
        0.001,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
    ),
    registry=REGISTRY,
)

# --- Jauges ---
MODEL_STATUS = Gauge(
    "kdrama_model_status",
    "Statut du modèle : 1 = entraîné et opérationnel, 0 = non disponible.",
    registry=REGISTRY,
)

PREDICTION_DRIFT = Gauge(
    "kdrama_model_prediction_drift",
    "Dérive de prédiction : écart entre la distribution actuelle "
    "et la distribution de référence (PSI - Population Stability Index).",
    labelnames=["model_type"],
    registry=REGISTRY,
)

ACTIVE_USERS = Gauge(
    "kdrama_api_active_users",
    "Nombre d'utilisateurs actifs (ayant fait au moins une requête "
    "dans la dernière fenêtre de temps).",
    registry=REGISTRY,
)

MODEL_ACCURACY = Gauge(
    "kdrama_model_accuracy",
    "Précision du modèle (RMSE sur les prédictions de test).",
    labelnames=["model_type"],
    registry=REGISTRY,
)

# --- Info ---
MODEL_INFO = Info(
    "kdrama_model_info",
    "Informations sur le modèle de recommandation.",
    registry=REGISTRY,
)


# ============================================================
# Gestionnaire de drift (dérive de prédiction)
# ============================================================


class DriftMonitor:
    """
    Surveille la dérive des prédictions (prediction drift).

    Le PSI (Population Stability Index) est utilisé pour quantifier
    l'écart entre la distribution de référence (au moment de l'entraînement)
    et la distribution actuelle des prédictions.

    Interprétation du PSI :
      - PSI < 0.1  : pas de dérive significative
      - 0.1 <= PSI < 0.25 : dérive modérée, surveillance requise
      - PSI >= 0.25 : dérive importante, ré-entraînement recommandé

    Attributes:
        reference_distribution: Distribution de référence (histogramme normalisé).
        window_size: Taille de la fenêtre glissante pour la distribution actuelle.
        current_predictions: File circulaire des prédictions récentes.
    """

    def __init__(
        self,
        reference_distribution: np.ndarray | None = None,
        window_size: int = 1000,
        num_bins: int = 10,
    ) -> None:
        """
        Initialise le moniteur de drift.

        Args:
            reference_distribution: Distribution de référence des prédictions.
                                     Si None, sera calculée à la première utilisation.
            window_size: Nombre de prédictions à conserver dans la fenêtre glissante.
            num_bins: Nombre de bins pour le calcul de l'histogramme.
        """
        self.reference_distribution = reference_distribution
        self.window_size = window_size
        self.num_bins = num_bins
        self.current_predictions: deque[float] = deque(maxlen=window_size)
        self._bins = np.linspace(0, 10, num_bins + 1)

    def add_prediction(self, score: float) -> None:
        """
        Ajoute une prédiction à la fenêtre de monitoring.

        Args:
            score: Score de prédiction (entre 0 et 10).
        """
        self.current_predictions.append(float(score))

    def set_reference(self, predictions: list[float] | np.ndarray) -> None:
        """
        Définit la distribution de référence à partir d'un ensemble
        de prédictions (généralement issues de l'ensemble de validation).

        Args:
            predictions: Liste ou array des scores de référence.
        """
        preds = np.array(predictions, dtype=float)
        hist, _ = np.histogram(preds, bins=self._bins)
        # Éviter les bins vides (ajout d'un epsilon)
        self.reference_distribution = hist / max(hist.sum(), 1) + 1e-8
        self.reference_distribution = (
            self.reference_distribution / self.reference_distribution.sum()
        )
        logger.info(
            "Distribution de référence définie avec %d prédictions.",
            len(preds),
        )

    def compute_psi(self) -> float:
        """
        Calcule le PSI (Population Stability Index) entre la distribution
        de référence et la distribution courante.

        Returns:
            Valeur du PSI (float). 0.0 si pas assez de données.
        """
        if self.reference_distribution is None or len(self.current_predictions) < 50:
            return 0.0

        current = np.array(list(self.current_predictions))
        current_hist, _ = np.histogram(current, bins=self._bins)
        current_dist = current_hist / max(current_hist.sum(), 1) + 1e-8
        current_dist = current_dist / current_dist.sum()

        # PSI = sum((current% - ref%) * ln(current% / ref%))
        psi = float(
            np.sum(
                (current_dist - self.reference_distribution)
                * np.log(current_dist / self.reference_distribution)
            )
        )

        return psi

    def get_drift_level(self) -> str:
        """
        Retourne le niveau de drift sous forme textuelle.

        Returns:
            "none", "moderate", ou "high".
        """
        psi = self.compute_psi()
        if psi < 0.1:
            return "none"
        elif psi < 0.25:
            return "moderate"
        else:
            return "high"


# ============================================================
# Gestionnaire de métriques global
# ============================================================


@dataclass
class MonitoringConfig:
    """Configuration du monitoring."""

    enable_drift_detection: bool = True
    drift_window_size: int = 1000
    alert_psi_threshold: float = 0.25
    alert_error_rate_threshold: float = 0.05  # 5% d'erreurs
    alert_latency_p99_threshold: float = 2.0  # 2 secondes


class ModelMonitor:
    """
    Gestionnaire central du monitoring du modèle d'IA.

    Centralise la collecte des métriques, la détection de drift,
    et la génération des alertes Prometheus/Grafana.

    Attributes:
        config: Configuration du monitoring.
        drift_monitor: Moniteur de drift de prédiction.
        _request_times: File des temps de requête pour calcul de latence.
    """

    def __init__(self, config: MonitoringConfig | None = None) -> None:
        """
        Initialise le gestionnaire de monitoring.

        Args:
            config: Configuration du monitoring. Utilise les valeurs par
                    défaut si None.
        """
        self.config = config or MonitoringConfig()
        self.drift_monitor = DriftMonitor(window_size=self.config.drift_window_size)
        self._request_times: deque[float] = deque(maxlen=10000)
        self._error_times: deque[float] = deque(maxlen=10000)

    def record_request(
        self,
        endpoint: str,
        method: str,
        status: int,
        latency: float,
    ) -> None:
        """
        Enregistre une requête API dans les métriques.

        Args:
            endpoint: Endpoint appelé (ex: /recommend).
            method: Méthode HTTP (GET, POST, etc.).
            status: Code de statut HTTP.
            latency: Latence en secondes.
        """
        REQUEST_COUNT.labels(endpoint=endpoint, method=method, status=str(status)).inc()
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency)
        self._request_times.append(time.time())

        if status >= 400:
            ERROR_COUNT.labels(
                endpoint=endpoint,
                error_type=f"HTTP_{status}",
            ).inc()
            self._error_times.append(time.time())

    def record_prediction(
        self,
        score: float,
        model_type: str = "HybridRecommender",
        mode: str = "recommend",
        inference_time: float = 0.0,
    ) -> None:
        """
        Enregistre une prédiction du modèle dans les métriques.

        Args:
            score: Score de la prédiction (0-10).
            model_type: Type du modèle.
            mode: Mode d'inférence (recommend, predict).
            inference_time: Temps d'inférence en secondes.
        """
        PREDICTION_COUNT.labels(model_type=model_type, mode=mode).inc()
        PREDICTION_SCORE_DISTRIBUTION.labels(model_type=model_type).observe(score)

        if inference_time > 0:
            MODEL_INFERENCE_TIME.labels(operation=mode).observe(inference_time)

        if self.config.enable_drift_detection:
            self.drift_monitor.add_prediction(score)

    def set_model_status(self, is_trained: bool) -> None:
        """
        Met à jour le statut du modèle.

        Args:
            is_trained: True si le modèle est entraîné et opérationnel.
        """
        MODEL_STATUS.set(1 if is_trained else 0)

    def set_model_info(
        self,
        model_type: str,
        alpha: float,
        embedding_model: str,
        num_dramas: int,
    ) -> None:
        """
        Met à jour les informations du modèle (métrique Info).

        Args:
            model_type: Type du modèle.
            alpha: Poids du content-based.
            embedding_model: Nom du modèle d'embedding.
            num_dramas: Nombre de dramas dans le catalogue.
        """
        MODEL_INFO.info(
            {
                "model_type": model_type,
                "alpha": str(alpha),
                "embedding_model": embedding_model,
                "num_dramas": str(num_dramas),
            }
        )

    def update_drift_metric(self, model_type: str = "HybridRecommender") -> float:
        """
        Met à jour la métrique de drift et retourne la valeur du PSI.

        Args:
            model_type: Type du modèle.

        Returns:
            Valeur du PSI (Population Stability Index).
        """
        psi = self.drift_monitor.compute_psi()
        PREDICTION_DRIFT.labels(model_type=model_type).set(psi)
        return psi

    def get_error_rate(self) -> float:
        """
        Calcule le taux d'erreur sur la dernière fenêtre.

        Returns:
            Taux d'erreur (entre 0.0 et 1.0).
        """
        if len(self._request_times) == 0:
            return 0.0
        return len(self._error_times) / max(len(self._request_times), 1)

    def get_latency_percentile(self, percentile: float = 0.99) -> float:
        """
        Calcule le percentile de latence.

        Args:
            percentile: Percentile à calculer (0.0 à 1.0).

        Returns:
            Valeur du percentile en secondes.
        """
        if not self._request_times:
            return 0.0
        # Note : en production, utiliser les histogrammes Prometheus
        # directement. Ceci est une approximation pour les alertes.
        return 0.0

    def check_alerts(self) -> list[dict[str, Any]]:
        """
        Vérifie toutes les conditions d'alerte et retourne les alertes actives.

        Alertes surveillées :
          1. Drift de prédiction (PSI > seuil)
          2. Taux d'erreur élevé (> seuil)
          3. Latence P99 élevée (> seuil)

        Returns:
            Liste des alertes actives avec niveau, message et valeur.
        """
        alerts: list[dict[str, Any]] = []

        # --- Alerte 1 : Drift de prédiction ---
        if self.config.enable_drift_detection:
            psi = self.update_drift_metric()
            if psi >= self.config.alert_psi_threshold:
                level = "critical" if psi >= 0.5 else "warning"
                alerts.append(
                    {
                        "name": "PredictionDriftHigh",
                        "level": level,
                        "message": f"High prediction drift: PSI = {psi:.4f}",
                        "value": psi,
                        "threshold": self.config.alert_psi_threshold,
                        "action": "Retrain the model with recent data.",
                    }
                )

        # --- Alerte 2 : Taux d'erreur ---
        error_rate = self.get_error_rate()
        if error_rate >= self.config.alert_error_rate_threshold:
            alerts.append(
                {
                    "name": "ErrorRateHigh",
                    "level": "critical",
                    "message": f"High error rate: {error_rate:.2%}",
                    "value": error_rate,
                    "threshold": self.config.alert_error_rate_threshold,
                    "action": "Check logs and API status.",
                }
            )

        return alerts

    def get_metrics(self) -> bytes:
        """
        Génère le contenu des métriques au format Prometheus.

        Returns:
            Bytes des métriques au format texte Prometheus.
        """
        return generate_latest(REGISTRY)

    def get_health_summary(self) -> dict[str, Any]:
        """
        Retourne un résumé de santé du modèle pour le dashboard.

        Returns:
            Dictionnaire avec les indicateurs clés.
        """
        psi = (
            self.drift_monitor.compute_psi()
            if self.config.enable_drift_detection
            else 0.0
        )
        drift_level = (
            self.drift_monitor.get_drift_level()
            if self.config.enable_drift_detection
            else "disabled"
        )

        return {
            "model_status": (
                "operational" if MODEL_STATUS._value.get() == 1 else "unavailable"
            ),
            "total_requests": len(self._request_times),
            "total_errors": len(self._error_times),
            "error_rate": round(self.get_error_rate(), 4),
            "prediction_drift_psi": round(psi, 4),
            "drift_level": drift_level,
            "active_predictions_in_window": len(self.drift_monitor.current_predictions),
            "alerts": self.check_alerts(),
        }


# ============================================================
# Règles d'alerte Prometheus (Grafana-compatible)
# ============================================================

ALERT_RULES = """
# ============================================================
# Règles d'alerte Prometheus pour le monitoring du modèle
# Fichier : alerts.yml (à placer dans /etc/prometheus/rules/)
# ============================================================

groups:
  - name: kdrama_model_alerts
    rules:
      # --- Alerte : Dérive de prédiction élevée ---
      - alert: PredictionDriftHigh
        expr: kdrama_model_prediction_drift > 0.25
        for: 5m
        labels:
          severity: warning
          service: kdrama-recommender
        annotations:
          summary: "High prediction drift"
          description: "The PSI (Population Stability Index) has been above 0.25 for 5 minutes. Retraining recommended."
          runbook_url: "https://wiki.internal/mlops/runbooks/drift"

      # --- Alerte : Dérive critique ---
      - alert: PredictionDriftCritical
        expr: kdrama_model_prediction_drift > 0.5
        for: 2m
        labels:
          severity: critical
          service: kdrama-recommender
        annotations:
          summary: "CRITICAL prediction drift"
          description: "PSI exceeds 0.5. The model must be retrained immediately."

      # --- Alerte : Taux d'erreur élevé ---
      - alert: HighErrorRate
        expr: |
          sum(rate(kdrama_api_errors_total[5m]))
          /
          sum(rate(kdrama_api_requests_total[5m]))
          > 0.05
        for: 2m
        labels:
          severity: critical
          service: kdrama-recommender
        annotations:
          summary: "High API error rate"
          description: "The error rate exceeds 5% over the last 5 minutes."

      # --- Alerte : Latence P99 élevée ---
      - alert: HighLatencyP99
        expr: |
          histogram_quantile(0.99,
            rate(kdrama_api_request_latency_seconds_bucket[5m]))
          > 2.0
        for: 5m
        labels:
          severity: warning
          service: kdrama-recommender
        annotations:
          summary: "High P99 latency"
          description: "P99 latency exceeds 2 seconds for 5 minutes."

      # --- Alerte : Modèle indisponible ---
      - alert: ModelUnavailable
        expr: kdrama_model_status == 0
        for: 1m
        labels:
          severity: critical
          service: kdrama-recommender
        annotations:
          summary: "AI model unavailable"
          description: "The recommendation model is not trained or has crashed."

      # --- Alerte : Aucune prédiction récente ---
      - alert: NoRecentPredictions
        expr: |
          increase(kdrama_model_predictions_total[10m]) == 0
        for: 10m
        labels:
          severity: warning
          service: kdrama-recommender
        annotations:
          summary: "No recent predictions"
          description: "No predictions have been generated in the last 10 minutes."
"""


# ============================================================
# Instance globale du moniteur
# ============================================================

# Singleton accessible par l'API
monitor = ModelMonitor()


def get_monitor() -> ModelMonitor:
    """
    Retourne l'instance globale du moniteur de modèle.

    Returns:
        Instance de ModelMonitor.
    """
    return monitor


def get_alert_rules() -> str:
    """
    Retourne les règles d'alerte Prometheus au format YAML.

    Returns:
        Chaîne YAML des règles d'alerte.
    """
    return ALERT_RULES


# ============================================================
# Tableau de bord Grafana (JSON)
# ============================================================

GRAFANA_DASHBOARD = {
    "dashboard": {
        "title": "K-Drama Recommender — AI Model Monitoring",
        "tags": ["mlops", "kdrama", "ai"],
        "timezone": "browser",
        "panels": [
            {
                "id": 1,
                "title": "Request latency (P50, P95, P99)",
                "type": "graph",
                "datasource": "Prometheus",
                "targets": [
                    {
                        "expr": "histogram_quantile(0.50, sum(rate(kdrama_api_request_latency_seconds_bucket[5m])) by (le))"
                    },
                    {
                        "expr": "histogram_quantile(0.95, sum(rate(kdrama_api_request_latency_seconds_bucket[5m])) by (le))"
                    },
                    {
                        "expr": "histogram_quantile(0.99, sum(rate(kdrama_api_request_latency_seconds_bucket[5m])) by (le))"
                    },
                ],
            },
            {
                "id": 2,
                "title": "Request count by endpoint",
                "type": "graph",
                "datasource": "Prometheus",
                "targets": [
                    {"expr": "sum(rate(kdrama_api_requests_total[5m])) by (endpoint)"},
                ],
            },
            {
                "id": 3,
                "title": "Prediction drift (PSI)",
                "type": "gauge",
                "datasource": "Prometheus",
                "targets": [
                    {"expr": "kdrama_model_prediction_drift"},
                ],
                "thresholds": [
                    {"value": 0.0, "color": "green"},
                    {"value": 0.1, "color": "yellow"},
                    {"value": 0.25, "color": "red"},
                ],
            },
            {
                "id": 4,
                "title": "Recommendation score distribution",
                "type": "histogram",
                "datasource": "Prometheus",
                "targets": [
                    {
                        "expr": "sum(rate(kdrama_model_prediction_score_distribution_bucket[5m])) by (le)"
                    },
                ],
            },
            {
                "id": 5,
                "title": "Error rate",
                "type": "graph",
                "datasource": "Prometheus",
                "targets": [
                    {
                        "expr": "sum(rate(kdrama_api_errors_total[5m])) / sum(rate(kdrama_api_requests_total[5m]))"
                    },
                ],
            },
            {
                "id": 6,
                "title": "Model status",
                "type": "stat",
                "datasource": "Prometheus",
                "targets": [
                    {"expr": "kdrama_model_status"},
                ],
            },
            {
                "id": 7,
                "title": "Model inference time",
                "type": "graph",
                "datasource": "Prometheus",
                "targets": [
                    {
                        "expr": "histogram_quantile(0.95, sum(rate(kdrama_model_inference_time_seconds_bucket[5m])) by (le))"
                    },
                ],
            },
        ],
        "time": {"from": "now-1h", "to": "now"},
        "refresh": "10s",
    }
}


def get_grafana_dashboard() -> dict[str, Any]:
    """
    Retourne la configuration JSON du tableau de bord Grafana.

    Returns:
        Dictionnaire de configuration du dashboard.
    """
    return GRAFANA_DASHBOARD
