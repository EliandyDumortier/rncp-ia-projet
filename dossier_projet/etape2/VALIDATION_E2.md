# Matrice de validation E2 — C6, C7 et C8

**Référentiel contrôlé** : titre Développeur en intelligence artificielle, évaluation E2

**Date de contrôle** : 3 septembre 2026

Cette matrice sépare les éléments présents dans le dépôt des preuves qui exigent encore une action dans le temps ou sur la plateforme Git distante.

## C6 — Organiser une veille technique et réglementaire

| N° | Critère reformulé | État | Preuve / action restante |
|---:|---|---|---|
| 1 | thème lié aux outils ou règles du projet | validé dans le dépôt | périmètre défini dans `src/synthese_veille.md` |
| 2 | au moins une heure de veille récurrente chaque semaine | partiel | planning et première séance dans `src/journal_veille.md`; poursuivre les entrées hebdomadaires |
| 3 | agrégation cohérente avec les sources et le budget | validé dans le dépôt | `src/veille_rss.py`, outil local gratuit hors infrastructure |
| 4 | synthèse accessible communiquée aux parties prenantes | partiel | document accessible présent; ajouter le lien de la pull request au journal après publication |
| 5 | informations partagées conformes au thème | validé dans le dépôt | bulletin et synthèse limités au service d'embeddings, à la recommandation et aux règles applicables |
| 6 | sources fiables, récentes, structurées et recoupées | validé dans le dépôt | matrice de fiabilité, dates de consultation et sources officielles dans la synthèse |

Correction à noter pour l'oral : l'ancienne collecte RSS contenait des faux positifs tels que « CIA » à cause du mot-clé court `ai`. Le filtre utilise désormais des limites de mots et un test de non-régression le prouve.

## C7 — Identifier le service d'IA approprié

| N° | Critère reformulé | État | Preuve |
|---:|---|---|---|
| 1 | besoin, objectifs et contraintes reformulés | validé dans le dépôt | `README.md` et `src/rapport_benchmark.md` |
| 2 | services étudiés et non étudiés listés | validé dans le dépôt | sections candidats et exclusions du benchmark |
| 3 | exclusions justifiées | validé dans le dépôt | raisons explicites pour AWS Bedrock, Voyage AI, modèles génératifs et Ollama |
| 4 | adéquation aux fonctionnalités demandées | validé dans le dépôt | colonne fonctionnelle et analyse par candidat |
| 5 | écoconception selon les informations disponibles | validé dans le dépôt | critère de sobriété, taille/dimension et inconnues fournisseur explicitées |
| 6 | contraintes et prérequis techniques | validé dans le dépôt | prérequis détaillés par candidat |
| 7 | conclusion sépare services adaptés et non adaptés, avantages et inconvénients | validé dans le dépôt | conclusion et analyse détaillée du benchmark |

Les notes sont des notes de décision pondérées. Elles ne sont pas présentées comme des mesures scientifiques. Les latences et qualités cloud non exécutées ont été supprimées.

## C8 — Installer et configurer le service d'IA retenu

| N° | Critère reformulé | État | Preuve |
|---:|---|---|---|
| 1 | service installé et accessible, authentification si nécessaire | validé localement | environnement `.venv`, chargement local sans authentification, exécution de `src/config_ia_service.py` |
| 2 | configuration conforme aux contraintes fonctionnelles et techniques | validé localement | embeddings CPU, similarité cosine, SVD/KNN et gestion d'erreurs testés |
| 3 | fonctions de monitorage disponibles opérationnelles | validé au niveau POC | journalisation du chargement, dimensions, latences et résultats; monitoring de production traité en E5 |
| 4 | documentation des accès, installation, tests, dépendances, interconnexions et données | validé dans le dépôt | sections correspondantes de `README.md` |
| 5 | documentation accessible | validé dans le dépôt | Markdown structuré, liens explicites, tableaux simples et recommandations d'export |

## Commandes de preuve exécutées

```powershell
cd dossier_projet/etape2
python -m unittest discover -s tests -v
python src/benchmark_ia.py
python src/config_ia_service.py
```

Résultats du 3 septembre 2026 : 5 tests de non-régression réussis; benchmark régénéré; tests content-based et collaboratif réussis sur CPU.

## Conclusion honnête

Les preuves techniques C7 et C8 sont présentes et exécutables. Le dispositif C6 est installé et sa première séance est documentée. Pour fermer complètement C6, il reste à accumuler les séances hebdomadaires réelles et à enregistrer la communication de la synthèse via la pull request ou un compte rendu adressé aux parties prenantes.
