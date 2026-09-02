# Validation CI/CD — Étape 4

Ce document décrit la chaîne réellement configurée pour l'application React.
Il ne remplace pas une preuve d'exécution GitHub Actions ou de déploiement
distant.

## Chaîne versionnée

Le workflow `.github/workflows/ci_cd_app.yml` s'exécute sur les pull requests
et les pushes vers `develop` et `main` qui modifient l'étape 4. Il utilise
Node.js 22 et enchaîne :

1. ESLint ; les avertissements existants sont affichés, sans modifier le code
   fonctionnel demandé.
2. Vitest et V8 coverage. Les seuils versionnés dans `vite.config.ts` sont :
   40 % pour lignes et instructions, 50 % pour branches, 35 % pour fonctions.
3. Construction Docker. Sur pull request, l'image est construite mais non
   publiée. Sur push de branche, elle est publiée dans GHCR avec le
   `GITHUB_TOKEN`.

Les tests unitaires utilisent des données locales déterministes : l'intégration
des API de données et IA est vérifiée séparément dans la stack Docker des étapes
1, 3 et 4, sans rendre la CI dépendante d'un serveur de développement.

## Reproduction locale

```bash
cd dossier_projet/etape4
npm ci
npm run lint
npm run test:coverage
npm run build
docker build -f docker/Dockerfile.app -t kdrama-app:4.0 .
docker run --rm -p 8080:80 kdrama-app:4.0
```

La disponibilité du conteneur se contrôle avec :

```bash
curl http://localhost:8080/health
```

## Résultat local du 2 septembre 2026

- lint exécuté : succès avec avertissements existants ;
- Vitest : 34 tests réussis ; couverture globale 42,04 % (seuils respectés) ;
- Vite production : build réussi ;
- Docker : image construite avec Node 22 et conteneur validé sur `/health` ;
  réponse `{"status":"ok","version":"4.0.0"}`.

## Limite à lever avant validation complète C19

La publication GHCR et le déploiement staging/production n'ont pas été exécutés
dans cet audit, faute de secrets et d'environnement distant fournis. Il faut
conserver le résultat du workflow GitHub Actions et une preuve du déploiement de
préproduction avant de qualifier la livraison distante de démontrée.
