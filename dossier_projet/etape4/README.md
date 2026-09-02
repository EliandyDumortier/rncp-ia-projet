# K-Drama IA — Application Web React de Recommandation par IA

**Étape 4** — Conception et développement d'une application intégrant un service d'IA
**Projet** : Système de recommandation de K-Dramas par Intelligence Artificielle
**Compétences RNCP** : C14, C15, C16, C17, C18, C19
**Branche Git** : `etape4/application-ia`

---

## Présentation

Cette application web **React** (TypeScript + Vite + Tailwind CSS) permet aux
utilisateurs de rechercher des K-Dramas (séries sud-coréennes), d'obtenir des
recommandations personnalisées générées par intelligence artificielle, de gérer
leurs favoris et de consulter leur profil.

L'application s'intègre au **service d'IA de recommandation** développé à l'étape 3
(API FastAPI exposant un modèle hybride de recommandation). Elle agit comme un
client web de cette API, offrant une interface accessible et ergonomique.

---

## Fonctionnalités

| Fonctionnalité | User story | Description |
|----------------|-----------|-------------|
| Recherche par mot-clé | US-01 | Recherche de dramas par titre ou synopsis |
| Filtre par genre | US-02 | Filtrage des résultats par genre |
| Dramas populaires | US-03 | Affichage des dramas les mieux notés sur l'accueil |
| Recommandations IA | US-04 | Recommandations personnalisées basées sur l'historique |
| Dramas similaires | US-05 | Recommandations basées sur un drama de référence |
| Gestion des favoris | US-07/08 | Ajout et suppression de favoris |
| Profil utilisateur | US-09 | Statistiques et historique |
| Authentification | US-10/11 | Connexion sécurisée via l'API IA (JWT) |

---

## Accessibilité

L'application est conforme au **RGAA 4.1** (niveau AA), adaptation française de
WCAG 2.1. Les critères implémentés incluent :

- Lien d'évitement (skip link) — RGAA 1.6
- Landmarks ARIA (`banner`, `navigation`, `main`, `contentinfo`)
- HTML sémantique et valide — RGAA 8.1
- `lang="en"` déclaré — RGAA 8.6
- Hiérarchie des titres (`h1` -> `h2` -> `h3`) — RGAA 9.1
- Listes sémantiques (`ul`, `li`) — RGAA 9.3
- Contrastes >= 4.5:1 — RGAA 3.1
- Focus visible (`:focus-visible`) — RGAA 7.1
- `aria-label` sur les boutons et liens — RGAA 7.1
- `aria-live` pour les messages flash et d'erreur — RGAA 7.3
- Texte alternatif sur les images — RGAA 1.2
- Labels associés aux champs de formulaire — RGAA 11.1
- Navigation clavier complète — RGAA 7.1
- Mouvements réduits respectés (`prefers-reduced-motion`)

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Navigateur (React + Tailwind CSS + ARIA)        │
└───────────────────┬─────────────────────────────┘
                    │ HTTP / fetch
                    ▼
┌─────────────────────────────────────────────────┐
│  API IA (FastAPI — étape 3)                      │
│  Endpoints : /auth/token, /recommend, /health    │
└─────────────────────────────────────────────────┘

Persistance locale :
  - JWT token : localStorage
  - Favoris : localStorage (par utilisateur)
```

---

## Structure du projet

```text
rncp-ia-projet/
├── .github/
│   └── workflows/
│       └── ci_cd_app.yml           # Pipeline CI/CD (C19) — root du repository
├── dossier_projet/
│   └── etape4/
│       ├── src/
│       │   ├── App.tsx                     # Application principale (routing, layout)
│       │   ├── main.tsx                    # Point d'entrée React
│       │   ├── index.css                   # Tailwind + animations
│       │   ├── types.ts                    # Types TypeScript
│       │   ├── data.ts                     # Catalogue de dramas + utilitaires
│       │   ├── api.ts                      # Client API IA (auth, recommandations)
│       │   ├── auth.tsx                    # Contexte d'authentification
│       │   ├── useFavorites.ts             # Hook de gestion des favoris
│       │   ├── components/
│       │   │   ├── Navbar.tsx              # Barre de navigation (RGAA)
│       │   │   ├── DramaCard.tsx           # Carte de drama (RGAA)
│       │   │   ├── FeatureCarousel.tsx     # Carrousel d'accueil
│       │   │   ├── FlashMessages.tsx       # Messages flash (aria-live)
│       │   │   ├── LoadingSkeleton.tsx     # Squelette de chargement
│       │   │   ├── SkipLink.tsx            # Lien d'évitement (RGAA 1.6)
│       │   │   └── DramaCard.test.tsx      # Tests du composant
│       │   ├── pages/
│       │   │   ├── HomePage.tsx            # Accueil (carrousel, populaires)
│       │   │   ├── SearchPage.tsx          # Recherche + filtre
│       │   │   ├── RecommendationsPage.tsx # Recommandations IA
│       │   │   ├── FavoritesPage.tsx       # Gestion des favoris
│       │   │   ├── ProfilePage.tsx         # Profil utilisateur
│       │   │   └── LoginPage.tsx           # Connexion
│       │   ├── test/
│       │   │   └── setup.ts                # Configuration vitest
│       │   ├── data.test.ts                # Tests des données et utilitaires
│       │   ├── app.test.tsx                # Tests d'intégration + accessibilité
│       │   ├── specifications_fonctionnelles.md  # C14 — User stories + RGAA
│       │   └── backlog_kanban.md           # C16 — Backlog Kanban
│       ├── docker/
│       │   └── Dockerfile.app              # Image Docker (node + nginx) (C19)
│       ├── package.json
│       ├── vite.config.ts
│       ├── tailwind.config.js
│       ├── tsconfig.json
│       ├── requirements.txt
│       └── README.md
```

---

## Installation et exécution

### Prérequis

- Node.js 22+
- L'API IA de l'étape 3 en cours d'exécution (par défaut sur `http://localhost:8001`)
- L'API DATA de l'étape 1 en cours d'exécution (par défaut sur `http://localhost:8000`)

### Installation locale

```bash
cd dossier_projet/etape4
npm install
npm run dev
```

L'application est accessible sur `http://localhost:5173` (Vite dev server).

### Exécution avec Docker

```bash
docker build -f docker/Dockerfile.app -t kdrama-app:4.0 .
docker run -p 8080:80 kdrama-app:4.0
```

L'application est accessible sur `http://localhost:8080`.
Le bon démarrage se vérifie avec `http://localhost:8080/health`.

---

## Tests

```bash
# Tous les tests avec couverture
npm run test:coverage

# Tests en mode watch
npm run test:watch

# Un fichier spécifique
npx vitest run src/data.test.ts
```

### Structure des tests

| Fichier | Couverture |
|---------|------------|
| `data.test.ts` | Données, utilitaires (truncate, stars, formatRating) |
| `app.test.tsx` | Navigation, recherche, accessibilité RGAA |
| `DramaCard.test.tsx` | Composant DramaCard (alt, aria-label, h3) |

---

## Configuration

### Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `VITE_API_IA_URL` | `http://localhost:8001` | URL de l'API IA (étape 3) |
| `VITE_API_DATA_URL` | `http://localhost:8000` | URL de l'API DATA (étape 1) |

---

## Sécurité

- **Mots de passe** : jamais stockés par l'application (délégués à l'API IA).
- **Tokens JWT** : stockés en localStorage, envoyés en header Authorization.
- **XSS** : React échappe automatiquement les variables (pas de dangerouslySetInnerHTML).
- **Validation** : validation des entrées côté client avant soumission.

---

## CI/CD

Le pipeline GitHub Actions (`.github/workflows/ci_cd_app.yml`) exécute :

1. **Lint** — eslint (style et qualité)
2. **Test** — vitest avec couverture >= 80 %
3. **Build** — Construction et push de l'image Docker vers ghcr.io
4. **Deploy** — Déploiement sur staging (develop) ou production (main)

---

*Étape 4 — RNCP AI Project — Système de recommandation de K-Dramas par IA.*
