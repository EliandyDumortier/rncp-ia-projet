# Matrice de validation E5 — C20 et C21

Cette matrice distingue volontairement cinq états. Un fichier présent ne constitue pas, à lui seul, une démonstration opérationnelle.

| Critère | Implémenté | Configuré | Testé | Documenté | Démontré | Preuve attendue |
|---|---:|---:|---:|---:|---:|---|
| C20.1 Métriques et seuils | Oui | Oui | À exécuter | Oui | À faire | Spécification, règles Prometheus |
| C20.2 Choix de l'outillage | Oui | s.o. | s.o. | Oui | À présenter | Spécification section 3 |
| C20.3 Outils opérationnels localement | Oui | Oui | À exécuter | Oui | À faire | `docker compose ps`, Prometheus Targets, Grafana |
| C20.4 Journalisation intégrée | Oui | Oui | À exécuter | Oui | À faire | Tests et logs JSON expurgés |
| C20.5 Alertes selon les seuils | Oui | Oui | À exécuter | Oui | À faire | Alertmanager et e-mail Mailpit |
| C20.6 Installation/configuration | Oui | Oui | À exécuter | Oui | À refaire depuis README | README et runbook |
| C20.7 Documentation accessible | Oui | s.o. | Relecture humaine | Oui | À présenter | Structure Markdown, langue claire, textes alternatifs |
| C21.1 Causes identifiées | Oui | s.o. | À exécuter | Oui | À présenter | Rapport d'incident |
| C21.2 Problème reproduit en développement | Oui | Oui | À exécuter | Oui | À faire | Test de régression avant/après |
| C21.3 Procédure de débogage documentée | Oui | s.o. | Relecture humaine | Oui | À présenter | Rapport d'incident et runbook |
| C21.4 Étapes de résolution explicitées | Oui | s.o. | À exécuter | Oui | À présenter | Rapport d'incident et tests |
| C21.5 Solution versionnée | En cours | s.o. | À exécuter | Oui | Après PR | Commits et pull request E5 |

Les colonnes « Testé » et « Démontré » ne passent à « Oui » qu'après exécution et conservation des preuves dans le dossier local `.validation/`, volontairement exclu de Git.
