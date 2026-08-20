# Étape 2 — Veille technique et intégration d'un service d'IA

**Projet** : K-Drama Recommendation System
**Branche Git** : `etape2/integration-ia`
**Compétences** : C6 (veille technique et réglementaire), C7 (identification de services d'IA), C8 (configuration d'un service d'IA)

---

## Table des matières

1. [Présentation](#présentation)
2. [Structure des fichiers](#structure-des-fichiers)
3. [Installation](#installation)
4. [Utilisation](#utilisation)
5. [Scripts détaillés](#scripts-détaillés)
6. [Résultats du benchmark](#résultats-du-benchmark)
7. [Conformité réglementaire](#conformité-réglementaire)

---

## Présentation

Cette étape met en place la veille technique et réglementaire nécessaire au
projet, identifie et compare les services d'IA disponibles pour le système de
recommandation de K-Dramas, puis installe et configure le service d'IA retenu.

Le système de recommandation utilise une approche hybride :
- **Filtrage basé sur le contenu** (*content-based*) : vectorisation des
  descriptions de séries avec `sentence-transformers` (Hugging Face) et calcul
  de similarité sémantique.
- **Filtrage collaboratif** (*collaborative filtering*) : identification
  d'utilisateurs similaires avec `scikit-learn` (TruncatedSVD + NearestNeighbors).

---

## Structure des fichiers

```
etape2/
├── README.md                  # Ce fichier
├── requirements.txt          # Dépendances Python (versions fixées)
└── src/
    ├── veille_rss.py          # Agrégateur RSS pour la veille (C6)
    ├── benchmark_ia.py        # Benchmark comparatif des services d'IA (C7)
    ├── config_ia_service.py   # Configuration et tests du service d'IA (C8)
    ├── synthese_veille.md     # Synthèse de la veille (3 mois) (C6)
    └── grille_benchmark.md    # Grille de benchmark scorée (C7)
```

---

## Installation

### Prérequis

- Python 3.10 ou supérieur
- pip (gestionnaire de paquets Python)
- Connexion internet (pour le téléchargement initial du modèle sentence-transformers)

### Étapes

```bash
# 1. Créer un environnement virtuel
python -m venv .venv

# 2. Activer l'environnement virtuel
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# 3. Installer les dépendances
pip install -r requirements.txt
```

Le modèle `all-MiniLM-L6-v2` (90 Mo) sera téléchargé automatiquement depuis le
Hugging Face Hub lors de la première exécution de `config_ia_service.py` ou
`benchmark_ia.py`.

---

## Utilisation

### 1. Lancer la veille RSS (C6)

```bash
python src/veille_rss.py
```

Le script :
- Lit les flux RSS configurés (blogs IA, sites réglementaires, communautés).
- Filtre les articles par mots-clés pertinents.
- Déduplique les articles (historique persistant en JSON).
- Génère un rapport Markdown (`src/rapport_veille.md`).

### 2. Lancer le benchmark des services d'IA (C7)

```bash
python src/benchmark_ia.py
```

Le script :
- Évalue 5 services d'IA sur 5 critères pondérés.
- Mesure la latence et la qualité (si sentence-transformers est installé).
- Calcule le coût théorique de chaque service.
- Génère un rapport Markdown (`src/rapport_benchmark.md`).

### 3. Configurer et tester le service d'IA (C8)

```bash
python src/config_ia_service.py
```

Le script :
- Charge le modèle `sentence-transformers` (content-based filtering).
- Entraîne le modèle SVD + KNN (collaborative filtering).
- Exécute des tests de validation (latence, qualité, gestion d'erreurs).
- Affiche un bilan des tests dans la console.

---

## Scripts détaillés

### veille_rss.py — Agrégateur RSS (C6)

Script d'automatisation de la veille technique et réglementaire.

**Fonctionnalités :**
- Lecture de 15+ flux RSS organisés en 4 catégories (modèles IA, services d'IA,
  réglementation, communauté).
- Filtrage par mots-clés (IA, recommandation, RGPD, AI Act, embeddings, etc.).
- Déduplication par hash SHA-256 (titre + URL), persistance en JSON.
- Génération d'un rapport Markdown trié par catégorie et par date.
- Gestion d'erreurs robuste (un flux indisponible ne bloque pas les autres).
- Logging configurable.

**Sorties :**
- `src/rapport_veille.md` — rapport des articles collectés.
- `src/veille_historique.json` — historique des hashes pour la déduplication.

### benchmark_ia.py — Benchmark des services d'IA (C7)

Script de benchmark comparatif et reproductible.

**Services évalués :**
1. OpenAI (`text-embedding-3-small`)
2. Hugging Face (`sentence-transformers` en local)
3. Cohere (`embed-multilingual-v3.0`)
4. Modèles locaux (Ollama + `nomic-embed-text`)
5. Google Vertex AI (`text-embedding-004`)

**Critères (pondérés) :**
- Coût (25 %), Latence (20 %), Qualité (25 %), Intégration (15 %), Conformité (15 %).

**Sorties :**
- `src/rapport_benchmark.md` — grille scorée et analyse détaillée.
- Résumé dans la console (notes globales).

### config_ia_service.py — Configuration du service d'IA (C8)

Script de configuration et de validation du service d'IA retenu.

**Composants configurés :**
- `ContentBasedRecommender` : encapsule sentence-transformers pour le
  filtrage basé sur le contenu (chargement lazy, embeddings en batch,
  recommandation par similarité cosine).
- `CollaborativeFilteringRecommender` : encapsule scikit-learn (TruncatedSVD +
  NearestNeighbors) pour le filtrage collaboratif (construction de matrice
  creuse, entraînement, prédiction de note, recommandation KNN).

**Tests inclus :**
- Test du content-based (indexation, recommandation par index et par requête).
- Test du collaborative (entraînement, prédiction, recommandation KNN).
- Mesure de latence (cible : < 200 ms content-based, < 500 ms collaborative).
- Gestion d'erreurs (modèle introuvable, matrice vide, index hors bornes).

---

## Résultats du benchmark

| Service | Note globale |
|---|:---:|
| 🥇 Hugging Face (sentence-transformers, local) | **4,55 / 5** |
| 🥈 Modèles locaux (Ollama) | 4,10 / 5 |
| 🥉 OpenAI | 3,85 / 5 |
| Google Vertex AI | 3,85 / 5 |
| Cohere | 3,60 / 5 |

**Service retenu** : Hugging Face `sentence-transformers` (inférence locale) +
`scikit-learn` (filtrage collaboratif).

Voir `src/grille_benchmark.md` pour la grille complète et la justification.

---

## Conformité réglementaire

Le choix de l'inférence locale garantit :
- **RGPD** : aucune donnée personnelle ne quitte le serveur (pas de transfert
  hors UE).
- **AI Act (art. 50)** : une mention « Recommandations par IA » sera affichée
  dans l'interface (Étape 3).
- **PIPA (Corée)** : pas de transfert international de données.

Voir `src/synthese_veille.md` pour le détail des findings réglementaires.

---

## Prochaines étapes (Étape 3)

- Intégration des classes `ContentBasedRecommender` et
  `CollaborativeFilteringRecommender` dans une API FastAPI.
- Filtrage hybride (combinaison pondérée des deux approches).
- Évaluation quantitative (NDCG@10, MAP, Recall@K).
- Interface de transparence (AI Act) et option de recommandation non
  personnalisée.
- Intégration de FAISS si le catalogue dépasse 50 000 séries.

---

*Étape 2 — Veille technique et intégration d'un service d'IA*
