# K-Drama IA — application web React

**Étape 4 — RNCP Développeur IA**
Application web du système de recommandation de K-Dramas. Elle couvre les
compétences C14 à C19 avec les éléments de conception, de développement, de
tests, de conteneurisation et de CI/CD disponibles dans ce dépôt.

## Rôle de l'application

L'interface est développée avec React, TypeScript, Vite et Tailwind CSS. Elle
permet de rechercher et filtrer des K-Dramas, consulter leur détail, gérer un
compte, des favoris, l'historique et des préférences, puis demander des
recommandations au modèle IA.

Elle consomme deux services du même projet :

```text
Navigateur → application React (étape 4)
                 ├─→ API de données et authentification (étape 1, port 8000)
                 └─→ API de recommandation IA (étape 3, port 8001)
                            └─→ modèle de recommandation
```

L'API de données est la source d'autorité pour les comptes et émet le JWT. Ce
jeton est ensuite transmis à l'API IA pour les routes protégées de
recommandation.

## Fonctionnalités

| Fonctionnalité | Référence |
|---|---|
| Recherche textuelle et filtrage par genre | US-01, US-02 |
| Catalogue et dramas populaires | US-03 |
| Recommandations personnalisées et similaires | US-04, US-05 |
| Authentification et inscription par JWT | US-10, US-11 |
| Favoris, notes, historique et préférences | US-07 à US-09 |
| Interface clavier, messages d'état et navigation accessible | Critères RGAA documentés |

Les spécifications fonctionnelles et les critères d'acceptation sont dans
[`src/specifications_fonctionnelles.md`](src/specifications_fonctionnelles.md).
Le backlog est dans [`src/backlog_kanban.md`](src/backlog_kanban.md).

## Accessibilité

L'application intègre notamment un lien d'évitement, des landmarks HTML/ARIA,
une hiérarchie de titres, des libellés de formulaire, un focus visible, des
messages `aria-live`, des textes alternatifs et la prise en charge de
`prefers-reduced-motion`. Ces mesures visent les critères RGAA 4.1 / WCAG 2.1
AA indiqués dans les spécifications. Elles ne remplacent pas un audit RGAA
manuel complet.

## Prérequis

- Node.js 22 ou supérieur ;
- npm ;
- Docker Desktop et Docker Compose, pour l'exécution conteneurisée ;
- les API des étapes 1 et 3 pour les fonctions nécessitant des données ou des
  recommandations réelles.

## Installation et exécution locale

```bash
cd dossier_projet/etape4
npm ci
npm run dev
```

Vite sert alors l'application sur `http://localhost:5173`.

Les valeurs par défaut appellent les services locaux :

| Variable de build Vite | Valeur par défaut | Usage |
|---|---|---|
| `VITE_API_DATA_URL` | `http://localhost:8000` | API de données et authentification (étape 1) |
| `VITE_API_IA_URL` | `http://localhost:8001` | API IA (étape 3) |

Les variables `VITE_*` sont intégrées au bundle au moment du build. Pour une
image Docker ou un déploiement, fournissez donc les URLs publiques des API avec
des arguments de build ; les modifier au démarrage du conteneur ne suffit pas.

## Qualité et tests

```bash
cd dossier_projet/etape4
npm run lint
npm run test:coverage
npm run build
```

Les tests Vitest couvrent le catalogue et ses utilitaires, le client des APIs,
le contexte d'authentification, les hooks de favoris et d'historique, ainsi que
les parcours essentiels et l'accessibilité de l'interface.

Au 2 septembre 2026, la validation locale a produit **44 tests réussis** et la
couverture V8 suivante :

| Indicateur | Résultat | Seuil bloquant |
|---|---:|---:|
| Lignes | 45,25 % | 44 % |
| Instructions | 45,25 % | 44 % |
| Branches | 60,54 % | 60 % |
| Fonctions | 43,16 % | 42 % |

Les seuils sont configurés dans [`vite.config.ts`](vite.config.ts). Les détails
de reproduction sont dans [`CI_CD_VALIDATION.md`](CI_CD_VALIDATION.md).

## Docker — application seule

Depuis `dossier_projet/etape4` :

```bash
docker build -f docker/Dockerfile.app -t kdrama-app:4.0 .
docker run --rm -p 8080:80 kdrama-app:4.0
```

Le conteneur nginx sert l'application sur `http://localhost:8080`. Sa sonde de
disponibilité est disponible sur :

```bash
curl http://localhost:8080/health
```

Pour construire l'image avec des URLs d'API différentes :

```bash
docker build -f docker/Dockerfile.app -t kdrama-app:4.0 \
  --build-arg VITE_API_DATA_URL=https://data.example.com \
  --build-arg VITE_API_IA_URL=https://model.example.com .
```

## Stack locale complète

Le fichier [`docker-compose.yml`](../../docker-compose.yml), à la racine du
dépôt, orchestre PostgreSQL, l'API de données (étape 1), l'API de modèle
(étape 3) et cette application web (étape 4).

```powershell
# À la racine rncp-ia-projet (première exécution)
Copy-Item docker.env.example docker.env
# Renseigner ensuite les quatre variables obligatoires dans docker.env
docker compose --env-file docker.env up --build
```

Services exposés localement :

| Service | URL |
|---|---|
| Application web | `http://localhost:8080` |
| API de données | `http://localhost:8000/health` |
| API IA | `http://localhost:8001/health` |
| PostgreSQL (hôte) | `localhost:5433` |

Pour arrêter la stack sans supprimer la base persistante :

```powershell
docker compose --env-file docker.env down
```

Le fichier `docker.env` contient les valeurs locales de `DB_PASSWORD`,
`JWT_SECRET`, `USER_PASSWORD` et `ADMIN_PASSWORD`. Il est ignoré
par Git. Le fichier versionné `docker.env.example` ne contient que les noms des
variables et des valeurs publiques de développement. Les variables Supabase
sont optionnelles : sans elles, l'application utilise l'API de données puis le
catalogue local en dernier recours.

## CI/CD

Le workflow versionné
[`/.github/workflows/ci_cd_app.yml`](../../.github/workflows/ci_cd_app.yml)
se déclenche, pour les fichiers de l'étape 4, sur :

- les pushes vers `etape4/integration-app`, `develop` et `main` ;
- les pull requests vers `develop` et `main`.

Il utilise Node.js 22 et enchaîne ESLint, Vitest avec les seuils ci-dessus,
l'archivage du rapport de couverture pendant 30 jours, puis la construction de
l'image Docker. Une pull request vérifie l'image sans la publier ; un push de
branche publie l'image dans GHCR avec le `GITHUB_TOKEN` du workflow.

Une exécution GitHub Actions a validé lint, tests avec couverture et build
Docker sur `etape4/integration-app` (commit `fdec327`). Les jobs de staging et
de production ne constituent pas encore un déploiement : ils nécessitent une
cible réelle et les secrets correspondants. Ne les considérez pas comme une
preuve de livraison distante avant cette configuration et son exécution.

## Sécurité et limites connues

- Les mots de passe ne sont pas stockés par le front-end.
- Le JWT est conservé dans `localStorage` et envoyé dans l'en-tête
  `Authorization` aux routes protégées.
- React échappe les valeurs affichées ; l'application n'utilise pas
  `dangerouslySetInnerHTML`.
- Les contrôles côté client améliorent l'expérience utilisateur, mais la
  validation et l'autorisation doivent rester appliquées par les API.
- Les avertissements ESLint existants et les avertissements de clés dupliquées
  dans le catalogue sont volontairement laissés intacts : aucune modification
  fonctionnelle de l'application n'est incluse dans cette mise à jour.

## Documentation associée

- [`CI_CD_VALIDATION.md`](CI_CD_VALIDATION.md) — reproduction et résultats de
  validation CI/CD locale ;
- [`src/specifications_fonctionnelles.md`](src/specifications_fonctionnelles.md)
  — besoins, scénarios et critères d'acceptation ;
- [`src/backlog_kanban.md`](src/backlog_kanban.md) — organisation agile ;
- `dossier_rapports/etape4/audit_etape4.md` — état de conformité et preuves à
  compléter pour le dossier RNCP.
