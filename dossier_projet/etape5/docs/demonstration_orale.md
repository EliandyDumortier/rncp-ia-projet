# Déroulé conseillé pour la démonstration E5

## Durée cible : 10 minutes

1. **Contexte et risques — 1 minute** : présenter les trois services et les métriques à risque.
2. **Architecture — 1 minute** : expliquer Prometheus, Grafana, Alertmanager, Mailpit et l'exporteur.
3. **Tableau de bord sain — 2 minutes** : montrer les trois services, la latence, les erreurs, l'état du modèle et le PSI.
4. **Incident supervisé — 2 minutes** : provoquer l'arrêt contrôlé du web, montrer l'alerte et l'e-mail, puis restaurer le service.
5. **Incident C21 — 2 minutes** : présenter E5-INC-001, sa reproduction avec une valeur fictive et le test de non-régression.
6. **Versionnement et bilan — 2 minutes** : afficher les commits, la pull request et la matrice des critères.

## Captures à conserver hors Git

- les trois services sains dans Grafana ;
- les deux cibles Prometheus à l'état `UP` ;
- l'alerte active puis résolue dans Alertmanager ;
- l'e-mail dans Mailpit ;
- la sortie du script de validation ;
- les tests des étapes 3 et 5 ;
- la pull request vers `develop`.

Chaque capture insérée dans le rapport doit posséder une légende descriptive et un texte alternatif. Les valeurs sensibles doivent être masquées avant la capture.
