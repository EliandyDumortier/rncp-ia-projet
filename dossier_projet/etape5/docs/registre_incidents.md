# Registre de suivi des incidents

## E5-INC-001 — Modèle indisponible après configuration Render

| Champ | Valeur |
|---|---|
| Statut | Corrigé, validation locale en cours |
| Priorité | Haute |
| Service | API du modèle |
| Détecté le | 3 septembre 2026 |
| Symptôme utilisateur | L'application chargeait, mais les recommandations et préférences échouaient |
| Signal technique | Entraînement du modèle en échec ; `/health` annonçait `degraded` avec HTTP 200 |
| Cause racine | `DATABASE_URL` enregistrée avec des guillemets littéraux dans Render |
| Risques associés | Faux positif du health check et exposition possible du mot de passe dans une exception |

### Procédure de débogage suivie

1. Vérifier séparément `/health` des API et le chargement de l'application web.
2. Comparer le code HTTP à la propriété JSON `status`.
3. Examiner les logs du démarrage du modèle sans recopier la chaîne de connexion dans le ticket.
4. Comparer la valeur Render à la syntaxe attendue : la valeur d'interface ne doit pas contenir les guillemets d'un fichier `.env`.
5. Reproduire localement avec une URL factice entourée de guillemets.
6. Ajouter un test de non-régression avant de modifier la validation de configuration.
7. Vérifier que l'erreur finale indique l'action corrective sans contenir le secret factice.
8. Vérifier qu'un modèle absent entraîne désormais HTTP 503.

### Critères de clôture

- la mauvaise configuration est rejetée avant l'appel à SQLAlchemy ;
- aucun secret factice n'apparaît dans le message d'erreur testé ;
- `/health` retourne 503 lorsque le modèle n'est pas prêt ;
- les tests de l'étape 3 et ceux du monitoring passent ;
- la correction est présente dans un commit et dans la pull request de l'étape 5.
