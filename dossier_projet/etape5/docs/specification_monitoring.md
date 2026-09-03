# Spécification du monitorage applicatif — Étape 5

## 1. Périmètre et finalité

Le monitorage couvre les trois services déjà livrés : API de données (étape 1), API du modèle d'IA (étape 3) et application web (étape 4). Il vise à détecter automatiquement une indisponibilité, une dégradation du modèle, une hausse des erreurs ou de la latence et une dérive des prédictions.

Les métriques n'emploient que des libellés techniques à cardinalité bornée (`service`, `endpoint`, `status`, `reason`). Aucun identifiant utilisateur, jeton, mot de passe, texte de recherche ou donnée personnelle n'est journalisé ou exposé à Prometheus.

## 2. Métriques, risques et seuils

| Métrique | Risque surveillé | Avertissement | Critique | Fenêtre |
|---|---|---:|---:|---:|
| `kdrama_service_up` | Service injoignable | — | `< 1` | 1 min |
| `kdrama_service_healthy` | Réponse 200 mais composant dégradé | — | `< 1` | 1 min |
| `kdrama_service_probe_latency_seconds` | Dégradation de l'expérience | `> 1 s` | `> 2 s` | 5 min |
| `kdrama_service_consecutive_failures` | Incident persistant | `>= 2` | `>= 3` | instantané |
| `kdrama_api_errors_total / kdrama_api_requests_total` | Hausse des erreurs modèle | `> 2 %` | `> 5 %` | 5 min |
| `kdrama_model_status` | Modèle non opérationnel | — | `< 1` | 1 min |
| `kdrama_model_prediction_drift` (PSI) | Données/prédictions différentes de la référence | `>= 0,10` | `>= 0,25` | fenêtre du modèle |
| `up` de Prometheus | Collecteur non scrappé | — | `< 1` | 2 min |

Les seuils de latence reprennent l'objectif déjà défini dans le monitoring du modèle. Les seuils PSI suivent l'interprétation intégrée à l'étape 3 : moins de 0,10 stable, 0,10 à 0,25 à surveiller, puis dérive importante.

## 3. Choix techniques

- **Prometheus** collecte les séries temporelles et évalue des règles d'alerte déclaratives. Son format est déjà exposé par l'API modèle.
- **Grafana** consolide la disponibilité, la latence, le taux d'erreur et l'état du modèle dans un tableau de bord provisionné et reproductible.
- **Alertmanager** regroupe, déduplique et route les alertes vers un webhook technique et un e-mail local.
- **Mailpit** reçoit les e-mails en démonstration locale sans envoyer de données à un tiers.
- **Exporteur FastAPI dédié** réalise des sondes fonctionnelles sur les trois services et produit des journaux JSON filtrés.

Cette architecture reste séparée de l'application : elle n'altère ni le Docker Compose de démonstration ni les services Render. Les images sont épinglées pour rendre l'installation reproductible.

## 4. Feedback loop MLOps

Prometheus collecte le PSI et l'état du modèle. Une dérive modérée déclenche une surveillance renforcée ; une dérive critique ouvre une alerte recommandant l'analyse des nouvelles données et, après validation humaine, un réentraînement. Aucun réentraînement automatique n'est lancé afin d'éviter de promouvoir un modèle non évalué.

## 5. Responsabilités et protection des données

L'exploitant consulte Grafana, qualifie l'alerte dans Alertmanager, suit le runbook et documente l'incident. Les logs sont conservés uniquement pendant l'exécution locale des conteneurs. Les secrets sont fournis par variables d'environnement, ne figurent ni dans les métriques, ni dans les logs, ni dans le dépôt Git.
