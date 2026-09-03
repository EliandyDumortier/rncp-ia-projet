# K-Drama IA — Étape 1 : données et API

Cette étape constitue la fondation de données du projet RNCP : collecte,
nettoyage et modélisation de K-Dramas, schéma PostgreSQL, protection des données
personnelles et API REST FastAPI. L'API est consommée par le modèle de l'étape
3 et par l'application React de l'étape 4.

## Responsabilités et architecture

```text
TMDB / MyDramaList / sources de sentiments
                 │
                 ▼
collecte et agrégation Python
                 │
                 ▼
PostgreSQL (schéma kdrama, scripts SQL versionnés)
                 │
                 ▼
FastAPI :8000 ──→ étape 3 (modèle) et étape 4 (front-end)
```

Les éléments principaux sont :

| Emplacement | Rôle |
|---|---|
| `src/data_collector.py` | collecte depuis les sources externes |
| `src/data_aggregator.py` | nettoyage, normalisation et agrégation |
| `src/database_schema.sql` | schéma PostgreSQL principal |
| `src/preferences_favoris_schema.sql` et scripts associés | extensions utilisateurs, préférences, favoris et historique |
| `src/sql_queries.py` | requêtes d'extraction et de contrôle |
| `src/api_server.py` | API REST, authentification et droits RGPD |
| `src/registre_rgpd.md` | registre des traitements et mesures RGPD |
| `tests/` | tests des collecteurs, de l'agrégateur et de l'API |

## Prérequis et environnement Python

Chaque étape possède son propre environnement virtuel. Créez donc celui-ci dans
`etape1/.venv`; il est exclu du dépôt par `.gitignore`.

```powershell
cd dossier_projet/etape1
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Sous Linux/macOS : `source .venv/bin/activate`.

## Configuration

Créez localement un fichier `.env` dans `dossier_projet/etape1`. Il ne doit
jamais être ajouté à Git.

```dotenv
# Sources externes (nécessaire seulement pour une collecte réelle)
TMDB_API_KEY=...

# PostgreSQL
DATABASE_URL=postgresql+psycopg2://kdrama:mot-de-passe@localhost:5433/kdrama

# API
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:8080

# Sécurité — remplacer impérativement en environnement partagé
JWT_SECRET=une-valeur-longue-aleatoire
JWT_EXPIRATION_MINUTES=60
```

`DATABASE_URL` doit correspondre au driver SQLAlchemy utilisé. Avec le Compose
racine, l'API utilise l'hôte interne `db:5432`; depuis la machine hôte,
PostgreSQL est publié sur le port `5433`.

## Base de données et schémas

Hors Docker, créez la base et appliquez les scripts SQL dans l'ordre suivant :

```bash
psql -U kdrama -d kdrama -f src/database_schema.sql
psql -U kdrama -d kdrama -f src/preferences_favoris_schema.sql
psql -U kdrama -d kdrama -f src/actor_preferences_by_name_schema.sql
psql -U kdrama -d kdrama -f src/genre_preferences_by_name_schema.sql
```

Ces scripts sont montés automatiquement lors de la première initialisation du
volume PostgreSQL par le `docker-compose.yml` racine. Si le volume existe déjà,
PostgreSQL ne rejoue pas les scripts d'initialisation : appliquez alors toute
évolution de schéma explicitement et sauvegardez les données avant intervention.

## Exécution locale

Lancez l'API depuis le dossier de l'étape 1 :

```powershell
cd dossier_projet/etape1
.\.venv\Scripts\Activate.ps1
uvicorn src.api_server:app --host 0.0.0.0 --port 8000 --reload
```

La documentation interactive est accessible sur `http://localhost:8000/docs`.
Le point de disponibilité est `http://localhost:8000/health`.

L'API fournit notamment l'inscription, la connexion JWT, le profil, les
K-Dramas paginés et recherchables, genres, acteurs, notes, favoris, historique,
préférences et opérations RGPD. Le contrat exact et les schémas de requête sont
publiés par OpenAPI sur `/docs`; utilisez cette source plutôt que de dupliquer
les charges utiles dans la documentation.

## Collecte et préparation

Les commandes suivantes s'exécutent dans l'environnement de l'étape 1. Elles
peuvent appeler des sources externes : utilisez une clé TMDB valide et respectez
leurs conditions d'utilisation et limites de requêtes.

```powershell
python src/data_collector.py
python src/data_aggregator.py
python src/sql_queries.py
```

Consultez les options `--help` des scripts avant une collecte complète. Ne
lancez pas de scraping intensif sans vérifier les limites et la configuration.

## Tests

```powershell
cd dossier_projet/etape1
.\.venv\Scripts\Activate.ps1
pytest tests -v
```

Les tests couvrent le collecteur, l'agrégateur, l'analyse de sentiments et
l'API. Ils doivent être exécutés avec une configuration de test isolée : ne
pointez pas les tests vers une base de production ni vers des identifiants réels.

## Docker — API seule

Depuis `dossier_projet/etape1` :

```bash
docker build -f docker/Dockerfile.api -t kdrama-data-api:local .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=postgresql+psycopg2://kdrama:mot-de-passe@host.docker.internal:5433/kdrama \
  -e JWT_SECRET=change-me \
  -e CORS_ORIGINS=http://localhost:5173,http://localhost:8080 \
  kdrama-data-api:local
```

Vérifiez le démarrage avec :

```bash
curl http://localhost:8000/health
```

L'image est construite en deux étapes sur Python 3.11 et s'exécute sous un
utilisateur non-root. Les valeurs d'exemple ne sont adaptées qu'au développement
local.

## Stack locale complète

Le fichier [`docker-compose.yml`](../../docker-compose.yml), à la racine du
dépôt, est la méthode recommandée pour intégrer les trois étapes : PostgreSQL,
l'API de données (E1), l'API de modèle (E3) et le front-end (E4).

```powershell
# à la racine rncp-ia-projet (première exécution)
Copy-Item docker.env.example docker.env
# Renseigner ensuite les quatre variables obligatoires dans docker.env
docker compose --env-file docker.env up --build
```

| Service | Adresse hôte |
|---|---|
| API de données | `http://localhost:8000` |
| API de modèle | `http://localhost:8001` |
| Application web | `http://localhost:8080` |
| PostgreSQL | `localhost:5433` |

Arrêtez sans effacer le volume de données avec
`docker compose --env-file docker.env down`. Les valeurs locales sensibles sont
chargées depuis `docker.env`, ignoré par Git; `docker.env.example` documente les
variables attendues sans contenir de secret.

## Sécurité, RGPD et traçabilité

- Les mots de passe sont hachés par l'API; ils ne sont pas exposés au front-end.
- L'authentification utilise des JWT signés, avec une durée configurable.
- Les contrôles d'autorisation restent côté API.
- Les routes de portabilité et d'effacement font partie du contrat RGPD.
- Le registre et les éléments de conformité sont documentés dans
  [`src/registre_rgpd.md`](src/registre_rgpd.md).
- Les secrets, `.env`, caches et environnements `.venv` sont exclus du dépôt.

## Documentation associée

- `src/database_schema.sql` — modèle de données et contraintes ;
- `src/sql_queries.py` — requêtes de contrôle/extraction ;
- `src/api_server.py` — implémentation de l'API ;
- `tests/` — tests automatisés ;
- `dossier_rapports/etape1/` — rapport RNCP et preuves à mettre à jour après
  la validation complète de l'intégration et du déploiement.
