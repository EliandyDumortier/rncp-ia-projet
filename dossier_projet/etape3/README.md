# K-Drama Recommender API — Étape 3 : MLOps & API de modèle d'IA

> Système de recommandation de K-Dramas (séries coréennes) propulsé par un modèle d'IA hybride, exposé via une API REST sécurisée, monitorée et déployée via une chaîne MLOps continue.

## 📋 Table des matières

- [Aperçu](#aperçu)
- [Architecture](#architecture)
- [Modèle d'IA hybride](#modèle-dia-hybride)
- [API REST (FastAPI)](#api-rest-fastapi)
- [Sécurité (JWT, OWASP)](#sécurité-jwt-owasp)
- [Monitoring (Prometheus, Grafana)](#monitoring-prometheus-grafana)
- [Tests automatisés](#tests-automatisés)
- [Pipeline MLOps (GitHub Actions)](#pipeline-mlops-github-actions)
- [Docker](#docker)
- [Installation et démarrage](#installation-et-démarrage)
- [Variables d'environnement](#variables-denvironnement)
- [Endpoints de l'API](#endpoints-de-lapi)
- [Compétences RNCP couvertes](#compétences-rncp-couvertes)

---

## Aperçu

Ce projet constitue l'**Étape 3** du projet RNCP AI, dédiée au **déploiement d'une API exposant un modèle d'IA**, à son **intégration**, au **monitoring**, aux **tests** et au **MLOps**.

Le système de recommandation de K-Dramas combine deux approches :

1. **Filtrage basé sur le contenu** (content-based) via `sentence-transformers` qui génère des embeddings sémantiques des synopsis de dramas.
2. **Filtrage collaboratif** (collaborative filtering) via `scikit-learn` (NearestNeighbors) sur la matrice d'interactions utilisateur-drama.

Le score final est une moyenne pondérée : `score = α × content_score + (1 - α) × collaborative_score`

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client (Web/Mobile)                    │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS + JWT
┌────────────────────────▼────────────────────────────────┐
│                   FastAPI (model_api.py)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  /auth   │  │/recommend│  │ /predict │  │ /health │ │
│  │ /token   │  │          │  │          │  │/metrics │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│       │             │             │             │       │
│  ┌────▼─────────────▼─────────────▼─────────────▼────┐ │
│  │           ModelManager (Singleton)                   │ │
│  └────────────────────┬────────────────────────────────┘ │
│                       │                                  │
│  ┌────────────────────▼────────────────────────────────┐ │
│  │       HybridRecommender (recommendation_model.py)   │ │
│  │  ┌──────────────┐  ┌──────────────────────────────┐ │ │
│  │  │ Content-Based│  │  Collaborative Filtering     │ │ │
│  │  │ Sentence-    │  │  scikit-learn NearestNeighbors│ │ │
│  │  │ Transformers │  │  (matrice utilisateur-drama) │ │ │
│  │  └──────────────┘  └──────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │       ModelMonitor (model_monitoring.py)             │ │
│  │  Prometheus metrics → /metrics endpoint              │ │
│  │  Drift detection (PSI) + Alert rules                  │ │
│  └─────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────┘
                         │ scrape
┌────────────────────────▼────────────────────────────────┐
│              Prometheus → Grafana Dashboard               │
└─────────────────────────────────────────────────────────┘
```

---

## Modèle d'IA hybride

**Fichier : `src/recommendation_model.py`**

### Caractéristiques

| Composant | Technologie | Description |
|-----------|-------------|-------------|
| Content-based | `sentence-transformers` (all-MiniLM-L6-v2) | Embeddings sémantiques des synopsis + genres |
| Collaborative | `scikit-learn` NearestNeighbors | Similarité cosinus entre utilisateurs |
| Fallback | TF-IDF (scikit-learn) | Si sentence-transformers indisponible |
| Sérialisation | `joblib` + `numpy` | Sauvegarde/chargement des artefacts |

### Utilisation

```python
from recommendation_model import HybridRecommender, load_real_data

# Chargement des données réelles depuis l'étape 1
# (PostgreSQL/Supabase si disponible, sinon fallback local configuré)
dramas_df, interactions_df = load_real_data(num_users=50)

# Entraînement
model = HybridRecommender(alpha=0.6)
metrics = model.train(dramas_df, interactions_df)

# Recommandations pour un utilisateur
results = model.recommend(user_id=1, top_k=10)

# Prédiction de note
score = model.predict(user_id=1, drama_id=1)

# Sauvegarde / chargement
model.save("./model_artifacts")
loaded = HybridRecommender.load("./model_artifacts")
```

> **Note sur les données** : Le catalogue de K-Dramas est chargé en
> priorité depuis PostgreSQL (étape 1). En environnement isolé (CI ou
> test local sans base), le loader peut utiliser un snapshot local
> (`LOCAL_DATA_SNAPSHOT_PATH`) ou un catalogue embarqué de secours.
> Les notes individuelles par utilisateur sont simulées de façon
> déterministe à partir de `note_moyenne`.

---

## API REST (FastAPI)

**Fichier : `src/model_api.py`**

L'API expose les endpoints suivants avec :

- **Authentification JWT** (HS256, expiration configurable)
- **Rate limiting** (slowapi) — protection contre les abus
- **Validation Pydantic** — rejet des entrées invalides
- **CORS configurable** — origines restreintes
- **Headers de sécurité OWASP** — X-Content-Type-Options, X-Frame-Options, etc.
- **Documentation OpenAPI** auto-générée (Swagger UI + ReDoc)

### Démarrage

```bash
cd src
python model_api.py
# API disponible sur http://localhost:8001
# Documentation sur http://localhost:8001/docs
```

---

## Sécurité (JWT, OWASP)

| Protection | Implémentation |
|------------|----------------|
| Authentification | JWT (PyJWT) avec expiration et signature HS256 |
| Rate limiting | slowapi — 100 req/min global, 30 req/min pour le modèle |
| Validation des entrées | Pydantic v2 avec contraintes (ge, le, min_length, max_length) |
| Injection SQL/XSS | Rejet des types invalides par Pydantic |
| Headers de sécurité | X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, CSP |
| CORS | Origines configurables via env vars |
| RBAC | Rôles user/admin avec contrôle d'accès |
| Force brute | Délai de 500ms + rate limit strict sur /auth/token |

---

## Monitoring (Prometheus, Grafana)

**Fichier : `src/model_monitoring.py`**

### Métriques collectées

| Métrique | Type | Description |
|----------|------|-------------|
| `kdrama_api_requests_total` | Counter | Nombre total de requêtes |
| `kdrama_api_request_latency_seconds` | Histogram | Latence des requêtes |
| `kdrama_api_errors_total` | Counter | Nombre d'erreurs |
| `kdrama_model_predictions_total` | Counter | Nombre de prédictions |
| `kdrama_model_prediction_score_distribution` | Histogram | Distribution des scores |
| `kdrama_model_inference_time_seconds` | Histogram | Temps d'inférence |
| `kdrama_model_status` | Gauge | Statut du modèle (1/0) |
| `kdrama_model_prediction_drift` | Gauge | PSI (dérive de prédiction) |

### Alertes

- **PredictionDriftHigh** : PSI > 0.25 (warning) / > 0.5 (critical)
- **HighErrorRate** : Taux d'erreur > 5%
- **HighLatencyP99** : Latence P99 > 2s
- **ModelUnavailable** : Statut modèle = 0
- **NoRecentPredictions** : Aucune prédiction en 10 min

### Dashboard Grafana

Le fichier `model_monitoring.py` exporte la configuration JSON du dashboard Grafana avec 7 panneaux : latence, requêtes, drift, distribution des scores, taux d'erreur, statut du modèle, temps d'inférence.

---

## Tests automatisés

**Fichier : `tests/test_model_api.py`**

### Couverture

| Catégorie | Nombre de tests | Description |
|-----------|----------------|-------------|
| Health endpoint | 6 | Format, statut, version, timestamp |
| Metrics endpoint | 4 | Format Prometheus, content-type |
| Auth endpoint | 6 | JWT valide/invalide, champs manquants |
| Recommend endpoint | 13 | Modes user/item, validation, format, tri, latence |
| Predict endpoint | 7 | Score valide, validation, latence |
| Model info | 2 | Avec/sans auth |
| Alerts (admin) | 3 | RBAC admin/user/anonyme |
| Sécurité OWASP | 7 | Token invalide, XSS, injection, headers |
| Modèle (unitaire) | 15 | Entraînement, inférence, sérialisation |
| Monitoring | 11 | Métriques, drift, alertes |
| Performance | 5 | Seuils de latence, concurrence |
| Validation edge cases | 7 | top_k=1, top_k=50, IDs extrêmes |
| OpenAPI | 5 | Spécification, sécurité, tags, docs |

### Exécution

```bash
pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=80
```

---

## Pipeline MLOps (GitHub Actions)

**Fichier : `.github/workflows/mlops_pipeline.yml`**

### Étapes

```
Lint (ruff + black + mypy)
  ↓
Tests (pytest + couverture ≥ 80%)
  ↓
Entraînement (génération des artefacts + tests de non-régression)
  ↓
Packaging (build Docker multi-stage + push vers GHCR)
  ↓
Déploiement (production, health check, notification Slack)
  ↓
Monitoring post-déploiement (vérification métriques Prometheus)
```

### Déclencheurs

- **Push** sur `etape3/mlops-modele` / `develop` / `main` : lint + tests + train + package.
- **Pull request** sur ces branches : lint + tests + train + package (build sans push d'image).
- **Déploiement** : uniquement sur push `develop` (staging) et push `main` (production).

---

## Docker

**Fichier : `docker/Dockerfile.model`**

### Caractéristiques

- **Multi-stage build** : builder (compilation) → runtime (léger)
- **Image de base** : `python:3.11-slim`
- **Utilisateur non-root** : sécurité OWASP
- **Healthcheck** : vérification automatique toutes les 30s
- **Gunicorn + Uvicorn workers** : 4 workers pour la concurrence
- **SBOM** : Software Bill of Materials généré à chaque build

### Build et run

```bash
# Build
docker build -t kdrama-recommender-api:local -f docker/Dockerfile.model .

# Run (test local sans base distante)
docker run --rm -p 8001:8001 \
  -e JWT_SECRET_KEY=test-secret \
  -e ADMIN_PASSWORD=admin123 \
  -e USER_PASSWORD=user123 \
  -e USE_LOCAL_DATA_SNAPSHOT=true \
  -e FALLBACK_TO_LOCAL_ON_DB_ERROR=true \
  --name kdrama-api-local \
  kdrama-recommender-api:local

# Health check
curl http://localhost:8001/health
```

---

## Installation et démarrage

### Prérequis

- Python 3.11+
- pip
- (Optionnel) Docker

### Installation locale

```bash
# 1. Cloner le dépôt
git clone https://github.com/rncp-ai/kdrama-recommender.git
cd kdrama-recommender/dossier_projet/etape3

# 2. Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Entraîner le modèle (optionnel : l'API le fait automatiquement)
cd src
python recommendation_model.py

# 5. Démarrer l'API
python model_api.py
```

### Démarrage avec Docker

```bash
docker build -t kdrama-recommender-api:local -f docker/Dockerfile.model .
docker run --rm -p 8001:8001 \
  -e JWT_SECRET_KEY=test-secret \
  -e ADMIN_PASSWORD=admin123 \
  -e USER_PASSWORD=user123 \
  -e USE_LOCAL_DATA_SNAPSHOT=true \
  -e FALLBACK_TO_LOCAL_ON_DB_ERROR=true \
  --name kdrama-api-local \
  kdrama-recommender-api:local
```

### Exécution des tests

```bash
pytest tests/ -v --cov=src --cov-report=term-missing --cov-fail-under=80
```

---

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `JWT_SECRET_KEY` | requis | Clé secrète pour signer les JWT |
| `JWT_EXPIRATION_HOURS` | `24` | Durée de validité des tokens (heures) |
| `API_HOST` | `0.0.0.0` | Hôte d'écoute |
| `API_PORT` | `8001` | Port d'écoute |
| `API_RELOAD` | `false` | Rechargement automatique (dev) |
| `LOG_LEVEL` | `info` | Niveau de logging |
| `API_RATE_LIMIT` | `100/minute` | Rate limit global |
| `MODEL_RATE_LIMIT` | `30/minute` | Rate limit pour /recommend et /predict |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,...` | Origines CORS autorisées |
| `ADMIN_PASSWORD` | requis | Mot de passe admin (démo) |
| `USER_PASSWORD` | requis | Mot de passe user (démo) |
| `SUPABASE_DB_URL` | optionnel | URL PostgreSQL Supabase (prioritaire) |
| `DATABASE_URL` | optionnel | URL PostgreSQL alternative |
| `USE_LOCAL_DATA_SNAPSHOT` | `false` | Force l'usage d'un snapshot local/embarqué |
| `FALLBACK_TO_LOCAL_ON_DB_ERROR` | `false` | Fallback snapshot/embarqué si DB indisponible |
| `LOCAL_DATA_SNAPSHOT_PATH` | vide | Chemin absolu vers un CSV local de catalogue |

---

## Endpoints de l'API

### Authentification

```bash
# Obtenir un token JWT
curl -X POST http://localhost:8001/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### Recommandations

```bash
# Recommandations pour un utilisateur
curl -X POST http://localhost:8001/recommend \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "top_k": 10}'

# Dramas similaires
curl -X POST http://localhost:8001/recommend \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"drama_id": 5, "top_k": 10}'
```

### Prédiction

```bash
curl -X POST http://localhost:8001/predict \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "drama_id": 5}'
```

### Monitoring

```bash
# Health check
curl http://localhost:8001/health

# Métriques Prometheus
curl http://localhost:8001/metrics

# Alertes (admin)
curl -H "Authorization: Bearer <admin_token>" http://localhost:8001/alerts
```

---

## Compétences RNCP couvertes

| Compétence | Description | Implémentation |
|------------|-------------|----------------|
| **C9** | Développer une API REST exposant un modèle d'IA avec authentification | FastAPI + JWT + OWASP + OpenAPI |
| **C10** | Intégrer une API d'IA dans une application existante | Endpoints REST documentés, CORS, SDK-ready |
| **C11** | Monitorer un modèle d'IA avec métriques, alertes et dashboard | Prometheus + Grafana + PSI drift detection |
| **C12** | Programmer des tests automatisés du modèle | pytest (90+ tests), couverture ≥ 80%, tests de non-régression |
| **C13** | Créer une chaîne de livraison continue MLOps | GitHub Actions : lint → test → train → package → deploy |

---

## Licence

MIT — Voir le fichier LICENSE pour plus de détails.

## Auteurs

Équipe Data Science / MLOps — Projet RNCP AI
