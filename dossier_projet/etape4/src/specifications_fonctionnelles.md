# Spécifications fonctionnelles — Étape 4

**Projet** : Système de recommandation de K-Dramas par Intelligence Artificielle
**Étape** : 4 — Conception et développement d'une application intégrant un service d'IA
**Compétence RNCP** : C14 — Analyser les besoins et rédiger des spécifications fonctionnelles
**Version** : 1.0
**Date** : Juillet 2025

---

## 1. Objectif du document

Ce document formalise les spécifications fonctionnelles de l'application web développée à l'étape 4. Il sert de **contrat** entre les parties prenantes (Product Owner, équipe de développement, validateur d'accessibilité) et alimente directement le backlog agile (`backlog_kanban.md`) et la suite de tests Vitest (`src/*.test.ts`, `src/*.test.tsx`).

Il couvre :

- Les **personas** (utilisateurs cibles).
- Les **user stories** au format standardisé, avec critères d'acceptation et critères d'accessibilité.
- Les **exigences non fonctionnelles** (performance, sécurité, accessibilité).
- Les **critères d'accessibilité RGAA 4.1 / WCAG 2.1 AA** applicables.

---

## 2. Personas

### 2.1 Persona 1 — Soo-jin (utilisatrice régulière)

- **Profil** : 28 ans, étudiante en échange en France.
- **Contexte d'usage** : Regarde 5 à 10 K-Dramas par an, utilise son smartphone le soir.
- **Besoins** : Recommandations personnalisées, recherche rapide, gestion de favoris.
- **Contraintes** : Connexion mobile parfois lente ; mode sombre pour préserver la batterie.
- **Accessibilité** : Aucune déficience, mais apprécie une interface claire et des contrastes suffisants.

### 2.2 Persona 2 — Marc (utilisateur débutant)

- **Profil** : 45 ans, professeur, découvre les K-Dramas.
- **Contexte d'usage** : Connaît peu le genre, cherche des recommandations de démarrage.
- **Besoins** : Page d'accueil avec dramas populaires, explications sur les genres, recherche par genre.
- **Contraintes** : Ordinateur de bureau, lunettes de lecture (presbytie).
- **Accessibilité** : Typographie lisible et contraste élevé nécessaires.

### 2.3 Persona 3 — Aïcha (utilisatrice malvoyante)

- **Profil** : 32 ans, développeuse, malvoyante.
- **Contexte d'usage** : Utilise un lecteur d'écran (NVDA / VoiceOver) et un agrandisseur.
- **Besoins** : Navigation entièrement au clavier, balises ARIA correctes, texte alternatif sur les images, contrastes conformes.
- **Contraintes** : Toute interaction nécessitant la souris est bloquante ; les images sans `alt` sont invisibles.
- **Accessibilité** : Conformité RGAA 4.1 niveau AA obligatoire pour utiliser l'application.

---

## 3. User stories

Chaque user story suit le format : *« En tant que [rôle], je veux [action], afin de [bénéfice]. »* Elle est accompagnée de critères d'acceptation (AC) mesurables et de critères d'accessibilité (ACC) référençant le RGAA 4.1.

### 3.1 Epic 1 — Recherche et découverte

#### US-01 — Recherche par mot-clé

> En tant qu'utilisateur, je veux effectuer une recherche par mot-clé afin de trouver un K-Drama précis.

- **Priorité** : Must
- **Story points** : 3
- **Critères d'acceptation** :
  - AC1 : Un champ de recherche est présent sur la page d'accueil et accessible via le menu.
  - AC2 : La recherche filtre les dramas dont le titre ou le synopsis contient le mot-clé (insensible à la casse).
  - AC3 : Les résultats sont affichés sous forme de cartes (titre, genres, note, image).
  - AC4 : Un message « Aucun résultat » s'affiche si la recherche ne retourne rien.
  - AC5 : La recherche est déclenchée par soumission du formulaire (Entrée ou clic sur le bouton).
- **Critères d'accessibilité** :
  - ACC1 : Le champ de recherche a un `<label>` associé (RGAA 11.1).
  - ACC2 : Le bouton de recherche a un `aria-label` explicite (RGAA 7.1).
  - ACC3 : Les résultats sont annoncés via `aria-live="polite"` (RGAA 7.3).

#### US-02 — Filtre par genre

> En tant qu'utilisateur, je veux filtrer les résultats par genre afin de cibler mes préférences.

- **Priorité** : Should
- **Story points** : 2
- **Critères d'acceptation** :
  - AC1 : Une liste déroulante de genres est disponible sur la page de recherche.
  - AC2 : La sélection d'un genre filtre les résultats en temps réel.
  - AC3 : L'option « Tous les genres » réinitialise le filtre.
- **Critères d'accessibilité** :
  - ACC1 : Le `<select>` a un `<label>` (RGAA 11.1).
  - ACC2 : Le changement de filtre est annonçable au lecteur d'écran (RGAA 7.3).

#### US-03 — Dramas populaires sur l'accueil

> En tant qu'utilisateur, je veux voir les dramas populaires sur la page d'accueil afin de découvrir des séries recommandées par la communauté.

- **Priorité** : Must
- **Story points** : 2
- **Critères d'acceptation** :
  - AC1 : La page d'accueil affiche les 6 dramas les mieux notés.
  - AC2 : Chaque carte affiche le titre, les genres, la note moyenne et une image.
  - AC3 : Un lien « Voir plus » redirige vers la page de recherche complète.
- **Critères d'accessibilité** :
  - ACC1 : Chaque image a un `alt` descriptif (RGAA 1.2).
  - ACC2 : La section a un titre `<h2>` (RGAA 9.1).

### 3.2 Epic 2 — Recommandations par IA

#### US-04 — Recommandations personnalisées

> En tant qu'utilisateur connecté, je veux obtenir des recommandations personnalisées basées sur mon historique afin de découvrir des séries adaptées à mes goûts.

- **Priorité** : Must
- **Story points** : 5
- **Critères d'acceptation** :
  - AC1 : La page `/recommendations` est accessible depuis le menu principal.
  - AC2 : L'utilisateur doit être connecté ; sinon, redirection vers `/login`.
  - AC3 : L'application appelle `POST /recommend` avec le `user_id` et `top_k=10`.
  - AC4 : Les 10 recommandations sont affichées en cartes (titre, genres, note prédite, score, synopsis).
  - AC5 : Chaque carte propose « Voir les détails » et « Ajouter aux favoris ».
  - AC6 : En cas d'indisponibilité API (HTTP 503), un message d'erreur clair s'affiche avec bouton « Réessayer ».
  - AC7 : Un squelette de chargement s'affiche pendant l'appel API.
- **Critères d'accessibilité** :
  - ACC1 : Liste `role="list"`, cartes `role="listitem"` (RGAA 7.1).
  - ACC2 : Chaque carte a un titre `<h3>` (RGAA 9.1).
  - ACC3 : Boutons avec `aria-label` explicites (RGAA 7.1).
  - ACC4 : État de chargement via `aria-live="polite"` (RGAA 7.3).
  - ACC5 : Contraste texte/fond ≥ 4.5:1 (RGAA 3.1).
  - ACC6 : Navigation clavier complète (RGAA 7.1).

#### US-05 — Dramas similaires

> En tant qu'utilisateur, je veux voir des dramas similaires à un drama que j'aime afin d'explorer un univers proche.

- **Priorité** : Should
- **Story points** : 3
- **Critères d'acceptation** :
  - AC1 : Depuis la fiche d'un drama, un bouton « Dramas similaires » appelle l'API en mode item (`drama_id`).
  - AC2 : 6 dramas similaires sont affichés.
- **Critères d'accessibilité** :
  - ACC1 : Le bouton a un `aria-label` (RGAA 7.1).

#### US-06 — Explicabilité des recommandations

> En tant qu'utilisateur, je veux comprendre pourquoi une recommandation m'est proposée afin de faire confiance à l'IA.

- **Priorité** : Could
- **Story points** : 3
- **Critères d'acceptation** :
  - AC1 : Chaque carte affiche le score de similarité et les genres communs.
  - AC2 : Une infobulle explique le mode (utilisateur / item).
- **Critères d'accessibilité** :
  - ACC1 : L'infobulle est accessible au clavier (RGAA 7.1).

### 3.3 Epic 3 — Gestion des favoris et profil

#### US-07 — Ajouter aux favoris

> En tant qu'utilisateur connecté, je veux ajouter un drama à mes favoris afin de le retrouver facilement.

- **Priorité** : Must
- **Story points** : 2
- **Critères d'acceptation** :
  - AC1 : Un bouton « Ajouter aux favoris » est présent sur chaque carte.
  - AC2 : L'ajout est persistant via l'API de données FastAPI et PostgreSQL ; un cache `localStorage` maintient temporairement l'interface hors ligne.
  - AC3 : Un message de confirmation s'affiche.
- **Critères d'accessibilité** :
  - ACC1 : Le bouton a un `aria-label` (RGAA 7.1).
  - ACC2 : Le message de confirmation est annoncé via `aria-live` (RGAA 7.3).

#### US-08 — Gérer les favoris

> En tant qu'utilisateur connecté, je veux consulter et supprimer mes favoris afin de gérer ma liste de visionnage.

- **Priorité** : Must
- **Story points** : 2
- **Critères d'acceptation** :
  - AC1 : La page `/favorites` liste les favoris de l'utilisateur connecté.
  - AC2 : Un bouton « Supprimer » est disponible par favori.
  - AC3 : Un message « Aucun favori » s'affiche si la liste est vide.
- **Critères d'accessibilité** :
  - ACC1 : Liste sémantique `<ul>`/`<li>` (RGAA 9.3).

#### US-09 — Profil utilisateur

> En tant qu'utilisateur, je veux consulter mon profil (historique, statistiques) afin de suivre mon activité.

- **Priorité** : Should
- **Story points** : 3
- **Critères d'acceptation** :
  - AC1 : La page `/profile` affiche le nom d'utilisateur, le nombre de favoris, le nombre de recommandations consultées.
  - AC2 : Un bouton « Se déconnecter » est présent.
- **Critères d'accessibilité** :
  - ACC1 : Les statistiques sont dans une liste descriptive `<dl>` (RGAA 9.3).

### 3.4 Epic 4 — Authentification

#### US-10 — Connexion

> En tant qu'utilisateur, je veux me connecter afin d'accéder aux fonctionnalités personnalisées.

- **Priorité** : Must
- **Story points** : 3
- **Critères d'acceptation** :
  - AC1 : La vue `login` propose un formulaire (nom d'utilisateur, mot de passe).
  - AC2 : L'authentification est déléguée à l'API de données (`POST /api/v1/auth/login`) qui émet un JWT également accepté par l'API IA.
  - AC3 : En cas d'erreur, un message s'affiche sans révéler la cause exacte (sécurité).
  - AC4 : Après connexion, l'utilisateur est redirigé vers la page demandée ou l'accueil.
- **Critères d'accessibilité** :
  - ACC1 : Champs avec `<label>` (RGAA 11.1).
  - ACC2 : Le message d'erreur est dans une `alert` `role="alert"` (RGAA 7.3).
  - ACC3 : Le formulaire est navigable au clavier (RGAA 7.1).

#### US-11 — Session persistante

> En tant qu'utilisateur, je veux rester connecté entre les sessions afin de ne pas ressaisir mon mot de passe.

- **Priorité** : Should
- **Story points** : 1
- **Critères d'acceptation** :
  - AC1 : Le JWT et l'identité minimale sont conservés dans `localStorage` afin de restaurer la session au rechargement.
  - AC2 : Le bouton « Se déconnecter » supprime le JWT et les données de session locales.
- **Critères d'accessibilité** : N/A.

---

## 4. Exigences non fonctionnelles

| Catégorie | Exigence | Cible |
|-----------|---------|-------|
| Performance | Time to Interactive (TTI) | < 3 s sur 4G |
| Performance | Latence API IA (p95) | < 500 ms |
| Disponibilité | Taux de disponibilité | 99,5 % |
| Sécurité | Stockage mots de passe | Hash bcrypt côté API de données ; aucun mot de passe stocké dans React |
| Sécurité | Tokens JWT | JWT émis par l'API de données, conservé dans `localStorage` et envoyé par en-tête `Authorization` |
| Sécurité | Protection CSRF | API sans cookie de session ; contrôle CORS restrictif sur les deux API |
| Sécurité | Protection XSS | Échappement React ; aucun `dangerouslySetInnerHTML` |
| Accessibilité | Conformité | RGAA 4.1 niveau AA |
| Compatibilité | Navigateurs | Chrome, Firefox, Safari, Edge (2 dernières versions) |
| Maintenabilité | Couverture de tests | ≥ 80 % |
| Observabilité | Logs | Structurés (JSON), niveau INFO en prod |

---

## 5. Critères d'accessibilité RGAA 4.1 (synthèse)

Les critères RGAA 4.1 les plus structurants pour l'application sont listés ci-dessous. Chaque critère est vérifié par test manuel (clavier + lecteur d'écran) et, quand possible, par test automatisé.

| Thème | Critère | Exigence | Implémentation |
|-------|---------|----------|----------------|
| 1. Architecture | 1.1 | Titre de page pertinent | `document.title` actualisé pour chaque vue React |
| 1. Architecture | 1.3 | Menu de navigation | `<nav aria-label>` |
| 1. Architecture | 1.6 | Lien d'évitement | Skip link en premier élément |
| 3. Couleurs | 3.1 | Contraste ≥ 4.5:1 | Variables CSS testées |
| 3. Couleurs | 3.2 | Info non portée par la couleur seule | Icônes + texte |
| 7. Scripts | 7.1 | Composants accessibles au clavier | `:focus-visible`, `tabindex` |
| 7. Scripts | 7.3 | Messages de statut annoncés | `aria-live` |
| 8. Éléments | 8.1 | HTML valide | HTML Vite et composants JSX/TSX valides |
| 8. Éléments | 8.6 | `lang` déclaré | `<html lang="en-us
| 9. Structuration | 9.1 | Hiérarchie des titres | `h1` → `h2` → `h3` |
| 9. Structuration | 9.3 | Listes sémantiques | `<ul>`, `<ol>`, `<li>` |
| 10. Présentation | 10.2 | Taille de texte modifiable | `rem`, zoom 200 % |
| 11. Formulaires | 11.1 | `<label>` associé | `for`/`id` |
| 11. Formulaires | 11.6 | Contrôle de saisie | Validation serveur |

---

## 6. Flux utilisateurs (parcours)

### 6.1 Parcours de recommandation (principal)

1. Utilisateur arrive sur `/` (accueil).
2. Clic sur « Mes recommandations » → `/recommendations`.
3. Si non connecté → redirection `/login` avec message flash.
4. Saisie des identifiants → validation via l'API de données → JWT partagé créé.
5. Retour à la vue des recommandations → appel API IA → affichage d'une sélection limitée à 4 résultats par section.
6. Utilisateur ajoute un drama aux favoris → message de confirmation.

### 6.2 Parcours de recherche

1. Utilisateur saisit un mot-clé sur l'accueil → `/search?q=...`.
2. Affichage des résultats filtrés.
3. Sélection d'un genre → filtrage en temps réel.
4. Clic sur un drama → fiche détaillée.

### 6.3 Parcours de gestion des favoris

1. Utilisateur connecté accède à `/favorites`.
2. Consultation de la liste.
3. Suppression d'un favori → mise à jour de la liste.

---

## 7. Matrice de traçabilité

| User story | Vue React | Composant principal | Test | Critère RGAA |
|-----------|-------|----------|------|--------------|
| US-01 | `search` | `SearchPage.tsx` | `app.test.tsx`, `data.test.ts` | 11.1, 7.3 |
| US-03 | `home` | `HomePage.tsx` | `app.test.tsx` | 1.2, 9.1 |
| US-04 | `recommendations` | `RecommendationsPage.tsx` | `api.test.ts` (parcours UI à compléter) | 7.1, 7.3, 9.1 |
| US-07 | cartes et vues privées | `DramaCard.tsx`, `useFavorites.ts` | `api.test.ts`, `hooks.test.ts` | 7.1, 7.3 |
| US-08 | `favorites` | `FavoritesPage.tsx` | `hooks.test.ts` (parcours UI à compléter) | 9.3 |
| US-09 | `profile` | `ProfilePage.tsx` | test d'intégration à compléter | 9.3 |
| US-10 | `login` | `LoginPage.tsx`, `auth.tsx` | `auth.test.tsx`, `api.test.ts` | 11.1, 7.3 |

---

*Fin du document de spécifications fonctionnelles — Étape 4.*
