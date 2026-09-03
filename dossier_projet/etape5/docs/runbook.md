# Runbook opérationnel du monitorage

## 1. Vérifications initiales

1. Ouvrir Grafana à l'adresse `http://localhost:3000`.
2. Consulter « K-Drama IA — Vue opérationnelle ».
3. Confirmer la joignabilité et la santé fonctionnelle des trois services.
4. Consulter Prometheus Targets à `http://localhost:9090/targets` si une série est absente.
5. Consulter Alertmanager à `http://localhost:9093` pour connaître l'état et l'heure de début.

Ne jamais copier un jeton JWT, une chaîne de connexion ou le corps d'une requête utilisateur dans une capture ou un ticket.

## 2. Qualification par alerte

### Service inaccessible ou dégradé

1. Identifier le `service` dans l'alerte.
2. Vérifier le code HTTP et le corps de son `/health`.
3. Consulter `docker compose ps` puis les dernières lignes de logs du seul service concerné.
4. Pour `model-api`, vérifier séparément `model_loaded`, `model_trained` et la cible `/metrics`.
5. Pour `data-api`, vérifier la propriété `database` sans afficher `DATABASE_URL`.
6. Corriger la cause, relancer le service et attendre la notification `RESOLVED`.

### Latence ou taux d'erreur élevé

1. Vérifier la durée et la portée du dépassement dans Grafana.
2. Comparer le débit de requêtes et le taux d'erreur sur la même fenêtre de cinq minutes.
3. Identifier l'endpoint, sans ajouter l'identifiant utilisateur aux labels Prometheus.
4. Reproduire avec une requête de test non personnelle avant toute modification.

### Dérive PSI

1. Entre 0,10 et 0,25, analyser les données récentes et renforcer la surveillance.
2. À partir de 0,25, suspendre toute promotion automatique du modèle.
3. Vérifier la qualité, la représentativité et la licéité des nouvelles données.
4. Réentraîner seulement après validation humaine, comparer les métriques et versionner l'artefact retenu.

## 3. Démonstration contrôlée d'une alerte

Cette procédure suppose que les deux stacks sont démarrées. Elle perturbe uniquement l'application web locale pendant environ une minute.

```powershell
docker stop kdrama-web-app
```

Attendre trois intervalles de sonde, puis vérifier :

- l'alerte `KDramaRepeatedProbeFailures` dans Alertmanager ;
- l'e-mail `[FIRING]` dans Mailpit à `http://localhost:8025` ;
- l'événement filtré à `http://localhost:9101/alerts`.

Restaurer immédiatement le service :

```powershell
docker start kdrama-web-app
```

Vérifier le retour à l'état sain et la notification de résolution. Une capture doit comporter un titre ou une légende textuelle ; la couleur seule ne doit pas porter l'information.

## 4. Escalade et clôture

Créer un ticket sur le modèle E5 incident, documenter les faits observés, la reproduction, la cause, la correction et les tests. Fermer seulement lorsque l'alerte est résolue, les tests passent et le correctif figure dans une pull request relue.
