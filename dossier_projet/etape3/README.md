# K-Drama Recommender API — Étape 3

Cette étape expose le modèle hybride de recommandation de K-Dramas via une API
FastAPI. Elle relie les données de l'étape 1 à l'interface React de l'étape 4
et fournit les éléments de tests, monitoring, packaging Docker et MLOps du
projet.

## Architecture et modèle

```text
API de données (étape 1 / PostgreSQL)
                 │
                 ▼
  HybridRecommender (étape 3)
  ├─ filtrage par contenu : embeddings sentence-transformers
  ├─ filtrage collaboratif : scikit-learn NearestNeighbors
  └─ repli TF-IDF et snapshot local si la source distante est indisponible
                 │
                 ▼
     API FastAPI :8001 ──→ application React (étape 4)
                 │
                 └─→ métriques Prometheus (/metrics)
```

Le modèle est implémenté dans `src/recommendation_model.py`. Il combine les
scores de contenu et collaboratifs avec le paramètre `alpha`. Les artefacts sont
sérialisés avec `joblib`/`numpy`; le chargement privilégie les données de
l'étape 1 puis un snapshot local ou un catalogue de secours lorsqu'un
environnement isolé ne fournit pas la base de données.

## API et sécurité

Le point d'entrée est `src/model_api.py`. Lancez le service puis consultez la
documentation OpenAPI sur `http://localhost:8001/docs`.

| Route | Rôle | Authentification |
|---|---|---|
| `GET /health` | état du service et du modèle | non |
| `GET /metrics` | métriques Prometheus | non |
| `POST /auth/token` | jeton JWT de démonstration | non |
| `POST /recommend` | recommandations personnalisées, similaires ou de découverte | JWT |
| `POST /predict` | prédiction de note | JWT |
| `GET /model/info` | métadonnées du modèle | JWT |
| `GET /alerts`, `GET /alerts/rules` | alertes et règles | rôle admin |

L'API applique une validation Pydantic, une limitation de débit, des origines
CORS configurables et des en-têtes de sécurité. Ces dispositifs complètent,
mais ne remplacent pas, la configuration de secrets, des origines et de la
base de données d'un environnement de production.

## Installation locale

Chaque étape possède son propre environnement Python : ne partagez pas celui
des autres dossiers.

```powershell
cd dossier_projet/etape3
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Sous Linux/macOS, activez-le avec `source .venv/bin/activate`.

Pour démarrer l'API :

```powershell
cd src
python model_api.py
```

L'API écoute par défaut sur `http://localhost:8001`. Le POC Streamlit est
disponible depuis le dossier de l'étape 3 avec :

```powershell
streamlit run streamlit_app.py
```

## Variables d'environnement principales

| Variable | Défaut / usage |
|---|---|
| `JWT_SECRET_KEY` | secret de signature JWT — valeur forte obligatoire hors développement |
| `JWT_EXPIRATION_HOURS` | durée de validité du JWT (24 par défaut) |
| `DATABASE_URL` / `SUPABASE_DB_URL` | accès aux données de l'étape 1 |
| `CORS_ALLOWED_ORIGINS` | origines front-end autorisées |
| `API_HOST`, `API_PORT` | hôte et port, par défaut `0.0.0.0:8001` |
| `USE_LOCAL_DATA_SNAPSHOT` | active un snapshot local en environnement isolé |
| `FALLBACK_TO_LOCAL_ON_DB_ERROR` | autorise le repli si la base est indisponible |
| `MODEL_OUTPUT_DIR` | répertoire des artefacts de modèle |

Ne versionnez jamais de secrets : `.env` et les environnements `.venv` sont
ignorés par Git.

## Tests et contrôle qualité

```powershell
cd dossier_projet/etape3
.\.venv\Scripts\Activate.ps1
pytest tests -v --cov=src --cov-report=term-missing --cov-fail-under=80
ruff check src tests
black --check --diff src tests
mypy src --ignore-missing-imports --no-strict-optional
```

Les tests couvrent le chargeur de données, le modèle, l'API, les routes de
monitoring, les contrôles JWT/RBAC et des scénarios de validation. La couverture
minimale configurée dans la chaîne MLOps est de 80 %. MyPy est informatif dans
le workflow (`continue-on-error`) ; Ruff et Black sont bloquants.

## Docker

Depuis `dossier_projet/etape3` :

```bash
docker build -f docker/Dockerfile.model -t kdrama-recommender-api:local .
docker run --rm -p 8001:8001 --env-file ../../docker.env \
  -e USE_LOCAL_DATA_SNAPSHOT=true \
  -e FALLBACK_TO_LOCAL_ON_DB_ERROR=true \
  kdrama-recommender-api:local
```

Vérifiez ensuite le conteneur :

```bash
curl http://localhost:8001/health
```

L'image est construite en deux étapes sur `python:3.11-slim`, démarre sous un
utilisateur non-root et inclut un healthcheck. Les valeurs d'exemple ci-dessus
ne doivent pas être utilisées en production.

## Stack locale E1 + E3 + E4

Le fichier [`docker-compose.yml`](../../docker-compose.yml) à la racine
orchestre PostgreSQL, l'API de données, cette API de modèle et l'application
web :

```powershell
# à la racine du dépôt (première exécution)
Copy-Item docker.env.example docker.env
# Renseigner ensuite les quatre variables obligatoires dans docker.env
docker compose --env-file docker.env up --build
```

Les services sont alors exposés sur les ports 8000 (data API), 8001 (model
API), 8080 (web) et 5433 (PostgreSQL depuis l'hôte). Les secrets locaux sont
centralisés dans `docker.env`, qui reste hors du dépôt.

## Pipeline MLOps

Le workflow [`mlops_pipeline.yml`](../../.github/workflows/mlops_pipeline.yml)
est déclenché pour les modifications de l'étape 3 sur les branches
`etape3/mlops-modele`, `develop` et `main`, ainsi que leurs pull requests. Il
enchaîne :

1. Ruff, Black et MyPy ;
2. pytest avec couverture minimale de 80 %, rapports JUnit et coverage
   archivés 30 jours ;
3. entraînement sur données réelles ou snapshot local, génération et validation
   d'artefacts ;
4. construction Docker puis publication dans GHCR pour les pushes (pas pour les
   pull requests) ;
5. jobs de staging/production et monitoring post-déploiement, à configurer avec
   une cible et des secrets réels.

Les étapes de déploiement du workflow affichent actuellement une simulation :
elles ne sont pas une preuve de déploiement distant. Une exécution GitHub
Actions réussie du pipeline MLOps est visible dans le dépôt; conservez son URL,
les artefacts et la preuve d'un futur déploiement réel pour le dossier RNCP.

## Documentation associée

- `src/recommendation_model.py` — modèle hybride et chargement des données ;
- `src/model_api.py` — contrat et implémentation de l'API ;
- `src/model_monitoring.py` — métriques, dérive et alertes ;
- `tests/` — tests automatisés ;
- `dossier_rapports/etape3/` — rapport et preuves à compléter après validation
  de l'intégration complète.
