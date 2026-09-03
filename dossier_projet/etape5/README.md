# Étape 5 — Monitorage et résolution d'incident

Cette étape répond aux compétences RNCP C20 et C21 : surveiller l'application d'intelligence artificielle et résoudre un incident technique documenté et versionné.

## État

L'implémentation supervise le système local complet sans remplacer son orchestration principale. Les preuves d'exécution sont générées dans `.validation/` et ne sont pas versionnées.

## Architecture

- exporteur de santé applicative sur le port `9101` ;
- Prometheus sur `9090` ;
- Grafana sur `3000` ;
- Alertmanager sur `9093` ;
- Mailpit sur `8025` pour démontrer les alertes e-mail.

Prometheus collecte directement `/metrics` de l'API modèle et les métriques produites par l'exporteur. Grafana est provisionné automatiquement. Alertmanager envoie chaque alerte à Mailpit et au webhook filtré de l'exporteur.

## Installation locale

Prérequis : Docker Desktop avec Compose, Python 3.12 et la stack applicative fonctionnelle.

Depuis la racine du dépôt, démarrer d'abord l'application :

```powershell
docker compose --env-file docker.env up -d --build
```

Créer l'environnement Python demandé pour l'étape 5 :

```powershell
py -3.12 -m venv dossier_projet/etape5/.venv
dossier_projet/etape5/.venv/Scripts/python.exe -m pip install -r dossier_projet/etape5/requirements-dev.txt
```

Puis démarrer le monitorage :

```powershell
docker compose -f dossier_projet/etape5/docker-compose.monitoring.yml up -d --build
```

| Interface | Adresse | Usage |
|---|---|---|
| Exporteur | `http://localhost:9101/targets` | Résultat normalisé des sondes |
| Prometheus | `http://localhost:9090/targets` | Collecte et règles |
| Grafana | `http://localhost:3000` | Dashboard sans connexion en local |
| Alertmanager | `http://localhost:9093` | Alertes actives et résolues |
| Mailpit | `http://localhost:8025` | Notifications e-mail locales |

## Validation

Sans dépendre des services démarrés :

```powershell
dossier_projet/etape5/.venv/Scripts/python.exe dossier_projet/etape5/scripts/validate_e5.py
```

Avec vérification de la stack en fonctionnement et d'une alerte déjà démontrée :

```powershell
dossier_projet/etape5/.venv/Scripts/python.exe dossier_projet/etape5/scripts/validate_e5.py --runtime
```

Le rapport est écrit dans `.validation/`. Ce dossier est privé et ignoré par Git. Un statut `MANUAL_REVIEW` est normal : le script ne prétend pas automatiser l'évaluation de la justification technique, de l'accessibilité ou de la qualité du rapport d'incident.

## Démonstration d'alerte

Suivre [le runbook](docs/runbook.md#3-démonstration-contrôlée-dune-alerte). L'arrêt temporaire du conteneur web déclenche une alerte après trois contrôles, un e-mail Mailpit et un événement webhook. Toujours redémarrer le service à la fin.

## Arrêt de la supervision

```powershell
docker compose -f dossier_projet/etape5/docker-compose.monitoring.yml down
```

Les volumes ne sont pas supprimés par cette commande. L'application principale reste active.

## Documentation et traçabilité RNCP

- [spécification des métriques et choix techniques](docs/specification_monitoring.md) ;
- [runbook opérationnel](docs/runbook.md) ;
- [registre de suivi E5-INC-001](docs/registre_incidents.md) ;
- [rapport de résolution](docs/rapport_incident.md) ;
- [matrice des 12 critères](docs/matrice_criteres.md) ;
- [contrôle d'accessibilité documentaire](docs/accessibilite_documentation.md) ;
- [déroulé de démonstration orale](docs/demonstration_orale.md).

## Production Render

La stack locale est la preuve opérationnelle minimale demandée par E5. Les URLs Render peuvent être fournies à l'exporteur via `DATA_API_URL`, `MODEL_API_URL` et `WEB_APP_URL` pour un contrôle ponctuel. Une surveillance permanente n'est pas activée ici afin de ne pas maintenir artificiellement éveillés les services gratuits Render.
