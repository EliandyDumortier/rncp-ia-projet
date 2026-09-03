# Matrice de validation E5 — C20 et C21

Cette matrice distingue volontairement cinq états. Un fichier présent ne constitue pas, à lui seul, une démonstration opérationnelle.

| Critère | Implémenté | Configuré | Testé | Documenté | Démontré | Preuve attendue |
|---|---:|---:|---:|---:|---:|---|
| C20.1 Métriques et seuils | Oui | Oui | Oui | Oui | Oui local | Spécification, 9 règles Prometheus validées |
| C20.2 Choix de l'outillage | Oui | s.o. | s.o. | Oui | À présenter | Spécification section 3 |
| C20.3 Outils opérationnels localement | Oui | Oui | Oui | Oui | Oui local | 5 conteneurs, cibles `UP`, dashboard provisionné |
| C20.4 Journalisation intégrée | Oui | Oui | Oui | Oui | Oui local | Tests et logs JSON expurgés |
| C20.5 Alertes selon les seuils | Oui | Oui | Oui | Oui | Oui local | Alerte réelle, webhook et e-mail Mailpit |
| C20.6 Installation/configuration | Oui | Oui | Oui | Oui | Oui local | README et runbook exécutés |
| C20.7 Documentation accessible | Oui | s.o. | Relecture humaine effectuée | Oui | À présenter | Contrôle d'accessibilité Markdown |
| C21.1 Causes identifiées | Oui | s.o. | Oui | Oui | À présenter | Rapport E5-INC-001 |
| C21.2 Problème reproduit en développement | Oui | Oui | Oui | Oui | Oui local | 4 tests de régression ciblés |
| C21.3 Procédure de débogage documentée | Oui | s.o. | Relecture effectuée | Oui | À présenter | Registre d'incident et runbook |
| C21.4 Étapes de résolution explicitées | Oui | s.o. | Oui | Oui | À présenter | Rapport d'incident et 120 tests E3 |
| C21.5 Solution versionnée | Oui local | s.o. | Oui | Oui | PR à créer | Commits dédiés ; pull request E5 à joindre |

Les preuves techniques détaillées sont générées dans le dossier local `.validation/`, volontairement exclu de Git. La pull request distante et les captures du rapport restent à produire par la candidate avant la remise.
