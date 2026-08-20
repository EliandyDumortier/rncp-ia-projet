# Étape 1 — Collecte et préparation des données

**Projet** : Système de recommandation de K-Dramas par intelligence artificielle
**Étape** : 1 — Collecte et préparation des données
**Branche Git** : `etape1/collecte-donnees`
**Compétences RNCP** : C1, C2, C3, C4, C5

---

## Table des matières

1. [Présentation](#présentation)
2. [Prérequis](#prérequis)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Structure du projet](#structure-du-projet)
6. [Utilisation](#utilisation)
7. [API REST](#api-rest)
8. [Tests](#tests)
9. [Conformité RGPD](#conformité-rgpd)

---

## Présentation

Cette étape constitue le socle du projet de recommandation de K-Dramas. Elle couvre :

- **C1** : Collecte de données depuis 3 sources (API REST TMDB, fichier CSV, scraping MyDramaList).
- **C2** : Requêtes SQL d'extraction (SELECT, JOIN, GROUP BY, agrégations, sous-requêtes, vues).
- **C3** : Agrégation, nettoyage et normalisation des données hétérogènes.
- **C4** : Base de données PostgreSQL conforme au RGPD (hachage, consentement, conservation, anonymisation).
- **C5** : API REST FastAPI avec authentification JWT, pagination et documentation OpenAPI.

---

## Prérequis

- **Python** 3.11 ou supérieur
- **PostgreSQL** 15 ou supérieur
- **Clé API TMDB** (gratuite) — [Obtenir une clé](https://www.themoviedb.org/settings/api)
- **Git** (pour cloner le dépôt)

---

## Installation

### 1. Cloner le dépôt et se placer sur la branche de l'étape 1

```bash
git clone <url-du-depot>
cd projet-kdrama
git checkout etape1/collecte-donnees
```

### 2. Créer et activer un environnement virtuel

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Installer les dépendances

```bash
cd dossier_projet/etape1
pip install -r requirements.txt
```

---

## Configuration

### 1. Créer le fichier `.env`

Copiez le fichier `.env.example` et remplissez les valeurs :

```bash
cp .env.example .env
```

### 2. Variables d'environnement requises

```env
# Clé API TMDB (gratuite — https://www.themoviedb.org/settings/api)
TMDB_API_KEY=votre_cle_api_tmdb

# Base de données PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/kdrama_db

# Sécurité JWT
JWT_SECRET=votre_secret_jwt_tres_long_et_aleatoire
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# Collecte (rate limiting)
SCRAPE_DELAY_SECONDS=2

# API
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### 3. Créer la base de données PostgreSQL

```bash
# Connexion à PostgreSQL
psql -U postgres

# Création de la base et de l'utilisateur
CREATE DATABASE kdrama_db;
CREATE USER kdrama_user WITH PASSWORD 'votre_mot_de_passe';
GRANT ALL PRIVILEGES ON DATABASE kdrama_db TO kdrama_user;
\q
```

### 4. Appliquer le schéma de base de données

```bash
psql -U kdrama_user -d kdrama_db -f src/database_schema.sql
```

---

## Structure du projet

```
dossier_projet/etape1/
├── src/
│   ├── data_collector.py      # Collecte (API TMDB, CSV, scraping MyDramaList)
│   ├── sql_queries.py          # Requêtes SQL d'extraction (C2)
│   ├── data_aggregator.py     # Agrégation, nettoyage, normalisation (C3)
│   ├── database_schema.sql     # Schéma DDL PostgreSQL conforme RGPD (C4)
│   ├── api_server.py           # API REST FastAPI avec JWT (C5)
│   └── registre_rgpd.md        # Registre des traitements RGPD
├── data/
│   ├── raw/                    # Données brutes collectées (JSON)
│   └── clean/                  # Données nettoyées (JSON + CSV)
├── requirements.txt            # Dépendances Python
└── README.md                   # Ce fichier
```

---

## Utilisation

### 1. Collecte des données (C1)

La collecte récupère les données depuis les trois sources et les sauvegarde au format JSON dans `data/raw/`.

```bash
# Collecte complète (TMDB + scraping MyDramaList)
python src/data_collector.py

# Collecte avec un fichier CSV spécifique
python src/data_collector.py --csv chemin/vers/kdrama_dataset.csv

# Collecte avec pagination limitée (tests rapides)
python src/data_collector.py --tmdb-pages 5 --scrape-pages 3
```

**Options disponibles :**

| Option | Description | Défaut |
|---|---|---|
| `--csv` | Chemin du fichier CSV à collecter | Aucun |
| `--tmdb-pages` | Nombre max de pages TMDB (20 résultats/page) | 50 |
| `--scrape-pages` | Nombre max de pages MyDramaList à scraper | 10 |
| `--output-dir` | Répertoire de sortie pour les données brutes | `data/raw` |

### 2. Requêtes SQL d'extraction (C2)

Le module `sql_queries.py` exécute les requêtes d'extraction sur la base PostgreSQL.

```bash
# Démonstration de toutes les requêtes
python src/sql_queries.py
```

Requêtes disponibles :
- Liste des K-Dramas (avec pagination)
- K-Dramas par année de diffusion
- K-Dramas et leurs genres (JOIN)
- K-Dramas et leurs acteurs principaux (JOIN)
- Notes des utilisateurs (JOIN multiple)
- Statistiques de notes par K-Drama (GROUP BY + AVG)
- Top des genres (GROUP BY + COUNT)
- Statistiques par année (GROUP BY + agrégations)
- K-Dramas au-dessus de la moyenne (sous-requête)
- Acteurs les plus productifs (HAVING + agrégation)
- Recherche par titre (ILIKE)
- Distribution des notes (CASE + GROUP BY)

### 3. Agrégation et nettoyage (C3)

Le pipeline d'agrégation charge les données brutes, les nettoie, les normalise, les fusionne et exporte le résultat.

```bash
# Exécution du pipeline complet
python src/data_aggregator.py
```

Le pipeline effectue :
1. Chargement des fichiers JSON bruts (`data/raw/`).
2. Normalisation des schémas (mapping des champs par source).
3. Nettoyage des chaînes, dates, notes et genres.
4. Suppression des entrées corrompues et doublons.
5. Fusion des sources par similarité de titre.
6. Export vers `data/clean/` (JSON + CSV) et base PostgreSQL.

### 4. Démarrage de l'API REST (C5)

```bash
# Démarrage du serveur de développement
python src/api_server.py

# Ou avec uvicorn directement
uvicorn src.api_server:app --reload --host 0.0.0.0 --port 8000
```

L'API est accessible aux adresses suivantes :
- **API** : http://localhost:8000
- **Documentation Swagger** : http://localhost:8000/docs
- **Documentation ReDoc** : http://localhost:8000/redoc
- **Schéma OpenAPI** : http://localhost:8000/openapi.json
- **Health check** : http://localhost:8000/health

---

## API REST

### Authentification

```bash
# Inscription
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "pseudonyme": "monpseudo",
    "email": "user@example.com",
    "mot_de_passe": "motdepasse123",
    "consentement_collecte": true,
    "consentement_marketing": false
  }'

# Connexion (retourne un token JWT)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=monpseudo&password=motdepasse123"

# Profil (avec token)
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <votre_token>"
```

### K-Dramas

```bash
# Liste paginée
curl "http://localhost:8000/api/v1/kdramas?page=1&page_size=20"

# Recherche
curl "http://localhost:8000/api/v1/kdramas?search=crash&page=1"

# Détails d'un K-Drama
curl http://localhost:8000/api/v1/kdramas/1

# Création (admin)
curl -X POST http://localhost:8000/api/v1/kdramas \
  -H "Authorization: Bearer <token_admin>" \
  -H "Content-Type: application/json" \
  -d '{"titre": "Nouveau K-Drama", "nb_episodes": 16}'
```

### Notes

```bash
# Ajouter une note (authentifié)
curl -X POST http://localhost:8000/api/v1/kdramas/1/notes \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"note": 9, "commentaire": "Excellent K-Drama !"}'
```

### Droits RGPD

```bash
# Portabilité des données (art. 20)
curl http://localhost:8000/api/v1/auth/me/export \
  -H "Authorization: Bearer <token>"

# Droit à l'effacement (art. 17)
curl -X DELETE http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <token>"
```

---

## Tests

### Vérifier que l'API fonctionne

```bash
# Health check
curl http://localhost:8000/health

# Réponse attendue :
# {"status": "ok", "database": "ok", "version": "1.0.0", "timestamp": "..."}
```

### Vérifier la base de données

```bash
psql -U kdrama_user -d kdrama_db -c "SELECT COUNT(*) FROM kdramas;"
psql -U kdrama_user -d kdrama_db -c "SELECT COUNT(*) FROM genres;"
psql -U kdrama_user -d kdrama_db -c "SELECT * FROM v_kdramas_populaires LIMIT 5;"
```

---

## Conformité RGPD

Le projet implémente les mesures RGPD suivantes :

| Mesure | Implémentation | Article RGPD |
|---|---|---|
| Hachage des emails | SHA-256 via pgcrypto | Art. 32 |
| Hachage des mots de passe | bcrypt via passlib | Art. 32 |
| Suivi du consentement | Colonnes `consentement_*` + `date_consentement` | Art. 6.1.a, 7 |
| Durée de conservation | `purger_comptes_inactifs()` (3 ans) | Art. 5.1.e |
| Droit à l'effacement | `anonymiser_utilisateur()` + endpoint DELETE | Art. 17 |
| Portabilité | `exporter_donnees_utilisateur()` + endpoint GET | Art. 20 |
| Journalisation | Table `journal_acces` | Art. 30 |
| Row Level Security | Politiques RLS PostgreSQL | Art. 32 |
| Anonymisation | Vue `v_utilisateurs_anonymises` | Art. 25 |

Voir le fichier `src/registre_rgpd.md` pour le registre complet des traitements.

---

## Contact

- **Projet** : Système de recommandation de K-Dramas par IA
- **Étape** : 1 — Collecte et préparation des données
- **Branche Git** : `etape1/collecte-donnees`

---

*Documentation générée dans le cadre du projet RNCP — Étape 1.*
