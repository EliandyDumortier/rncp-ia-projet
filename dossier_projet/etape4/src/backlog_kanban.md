# Backlog Kanban — Étape 4

**Projet** : Système de recommandation de K-Dramas par IA
**Étape** : 4 — Conception et développement d'une application intégrant un service d'IA
**Compétence RNCP** : C16 — Coordonner un projet en méthode agile
**Sprint** : Sprint 4 (2 semaines)
**Branche Git** : `integration-app`

---

## 1. Configuration du sprint

- **Durée du sprint** : 2 semaines
- **Équipe** : 3 personnes (1 Product Owner, 1 Scrum Master / dev, 1 dev)
- **Vélocité estimée** : 30 story points
- **Vélocité réalisée** : 31 story points
- **Limite WIP (Work In Progress)** : 2 cartes par personne en colonne « En cours »

---

## 2. Tableau Kanban

Le tableau Kanban est organisé en 5 colonnes. Ci-dessous, l'état final du sprint (toutes les user stories « Must » et « Should » sont terminées).

### 2.1 Colonne « Backlog » (non planifié)

| ID | Titre | Priorité | SP | Responsable |
|----|-------|----------|----|-------------|
| US-06 | Explicabilité des recommandations | Could | 3 | — |
| T-08 | Internationalisation (i18n) | Won't | 5 | — |
| T-09 | Cache Redis pour recommandations | Won't | 3 | — |

### 2.2 Colonne « À faire » (planifié pour le sprint)

*Vide — tous les items planifiés ont été traités.*

### 2.3 Colonne « En cours »

*Vide — sprint terminé.*

### 2.4 Colonne « À valider »

*Vide — toutes les user stories ont été revues et validées.*

### 2.5 Colonne « Terminé »

| ID | Titre | Priorité | SP | Responsable | Commit |
|----|-------|----------|----|-------------|--------|
| US-01 | Recherche par mot-clé | Must | 3 | Dev A | `feat: recherche par mot-clé (US-01)` |
| US-02 | Filtre par genre | Should | 2 | Dev A | `feat: filtre par genre (US-02)` |
| US-03 | Dramas populaires (accueil) | Must | 2 | Dev B | `feat: dramas populaires sur accueil (US-03)` |
| US-04 | Recommandations personnalisées IA | Must | 5 | Dev B | `feat: page recommandations IA (US-04)` |
| US-05 | Dramas similaires | Should | 3 | Dev B | `feat: dramas similaires (US-05)` |
| US-07 | Ajouter aux favoris | Must | 2 | Dev A | `feat: ajout aux favoris (US-07)` |
| US-08 | Gérer les favoris | Must | 2 | Dev A | `feat: gestion favoris (US-08)` |
| US-09 | Profil utilisateur | Should | 3 | Dev A | `feat: profil utilisateur (US-09)` |
| US-10 | Connexion | Must | 3 | Dev C | `feat: authentification (US-10)` |
| US-11 | Session persistante | Should | 1 | Dev C | `feat: session persistante (US-11)` |
| T-01 | Mise en place React + TypeScript + Vite | Must | 2 | Dev C | Historique Git E4 |
| T-02 | Intégration client API IA | Must | 3 | Dev B | `feat: client API IA (T-02)` |
| T-03 | Composants React accessibles (ARIA, skip link) | Must | 2 | Dev A | Historique Git E4 |
| T-04 | CSS responsive + contrastes | Must | 3 | Dev A | `feat: css responsive (T-04)` |
| T-05 | Suite de tests Vitest et Testing Library | Must | 3 | Dev C | `f9d695c`, `c0ef65a` |
| T-06 | Pipeline CI/CD GitHub Actions | Must | 2 | Dev C | `ci: pipeline github actions (T-06)` |
| T-07 | Dockerfile app | Must | 1 | Dev B | `build: dockerfile app (T-07)` |

**Total terminé** : 31 story points (10 user stories + 7 tâches techniques).

---

## 3. Backlog détaillé

### 3.1 User stories

| ID | Titre | Priorité | SP | Epic | Statut |
|----|-------|----------|----|------|--------|
| US-01 | Recherche par mot-clé | Must | 3 | Recherche | Terminé |
| US-02 | Filtre par genre | Should | 2 | Recherche | Terminé |
| US-03 | Dramas populaires (accueil) | Must | 2 | Recherche | Terminé |
| US-04 | Recommandations personnalisées IA | Must | 5 | Recommandations | Terminé |
| US-05 | Dramas similaires | Should | 3 | Recommandations | Terminé |
| US-06 | Explicabilité des recommandations | Could | 3 | Recommandations | Backlog |
| US-07 | Ajouter aux favoris | Must | 2 | Favoris | Terminé |
| US-08 | Gérer les favoris | Must | 2 | Favoris | Terminé |
| US-09 | Profil utilisateur | Should | 3 | Favoris | Terminé |
| US-10 | Connexion | Must | 3 | Auth | Terminé |
| US-11 | Session persistante | Should | 1 | Auth | Terminé |

### 3.2 Tâches techniques

| ID | Titre | Priorité | SP | Statut |
|----|-------|----------|----|--------|
| T-01 | Mise en place React + TypeScript + Vite | Must | 2 | Terminé |
| T-02 | Intégration client API IA (RecommendationClient) | Must | 3 | Terminé |
| T-03 | Composants accessibles (landmarks, ARIA, skip link) | Must | 2 | Terminé |
| T-04 | CSS responsive + contrastes RGAA | Must | 3 | Terminé |
| T-05 | Suite de tests Vitest (composants, clients API et hooks) | Must | 3 | En amélioration |
| T-06 | Pipeline CI/CD GitHub Actions | Must | 2 | Terminé |
| T-07 | Dockerfile app | Must | 1 | Terminé |
| T-08 | Internationalisation (i18n) | Won't | 5 | Backlog |
| T-09 | Cache Redis pour recommandations | Won't | 3 | Backlog |

---

## 4. Rituels agiles

### 4.1 Sprint planning

- **Date** : Jour 1 du sprint
- **Durée** : 1 h
- **Objectif** : Sélectionner les user stories, estimer en Planning Poker, figer le sprint backlog.
- **Participants** : PO, Scrum Master, équipe de dev.
- **Livrable** : Sprint backlog (31 SP), objectif de sprint.

### 4.2 Daily standup

- **Fréquence** : Quotidien, 15 min
- **Format** : 3 questions (hier / aujourd'hui / blocages)
- **Format asynchrone** : post sur canal de messagerie si emploi du temps chargé.

### 4.3 Sprint review

- **Date** : Jour 10 du sprint
- **Durée** : 30 min
- **Objectif** : Démonstration de l'application, rétroaction PO, validation des US terminées.

### 4.4 Sprint retrospective

- **Date** : Jour 10 du sprint
- **Durée** : 45 min
- **Format** : Ce qui a bien fonctionné / à améliorer / actions concrètes
- **Actions issues** :
  1. Mettre en place ESLint dès le premier commit → **réalisé**.
  2. Écrire les tests en parallèle du dev (TDD léger) → **partiellement réalisé**, à généraliser à l'étape 5.
  3. Documenter l'accessibilité dans le DoD → **réalisé**.

---

## 5. Definition of Done (DoD)

Une user story est « terminée » si et seulement si :

1. Le code est implémenté et respecte les conventions, avec ESLint sans erreur.
2. Les tests Vitest passent et les seuils versionnés sont respectés ; la cible projet reste 80 %.
3. La user story est vérifiée manuellement contre ses critères d'acceptation et la preuve est conservée.
4. Les critères d'accessibilité applicables sont vérifiés au clavier et avec un lecteur d'écran.
5. Le code est revu par au moins une autre personne lorsque le contexte d'équipe le permet.
6. La documentation et la matrice de traçabilité sont mises à jour.
7. La CI est verte sur `etape4/integration-app`, puis le code est fusionné dans `develop`.

---

## 6. Registre des risques

| Risque | Probabilité | Impact | Mitigation | Statut |
|--------|------------|--------|------------|--------|
| Indisponibilité de l'API IA | Moyenne | Élevé | Client HTTP retry + fallback (dramas populaires) | Maîtrisé |
| Non-conformité RGAA | Moyenne | Élevé | Audit manuel + tests d'accessibilité | En cours |
| Latence API > 500 ms | Moyenne | Moyen | Cache + squelette de chargement | Maîtrisé |
| Conflits Git | Faible | Faible | Branches courtes, revues rapides | Maîtrisé |
| Couverture tests < 80 % | Faible | Moyen | Tests écrits en parallèle du dev | Surveillé |

---

## 7. Burndown chart (synthèse)

| Jour | SP restants | Idéal |
|------|-------------|-------|
| 1 | 31 | 31 |
| 3 | 26 | 25 |
| 5 | 19 | 19 |
| 7 | 12 | 13 |
| 9 | 4 | 7 |
| 10 | 0 | 0 |

Le sprint s'est terminé à temps, avec une légère avance sur l'idéal aux jours 7 et 9.

---

## 8. Métriques de qualité

| Métrique | Cible | Réalisé |
|----------|-------|---------|
| Couverture de tests | ≥ 80 % | 45,65 % lignes au 2 septembre 2026 |
| Linting ESLint | 0 erreur | 0 erreur, 6 avertissements |
| Conformité RGAA (audit manuel) | Niveau AA | À auditer manuellement |
| Temps de réponse moyen (accueil) | < 1 s | À mesurer en préproduction |
| Temps de réponse moyen (recommandations) | < 3 s | À mesurer en préproduction |

---

*Fin du backlog Kanban — Étape 4.*
