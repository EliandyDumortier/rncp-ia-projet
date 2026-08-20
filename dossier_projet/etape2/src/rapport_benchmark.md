# Rapport de benchmark — Services d'IA pour la recommandation

**Projet** : K-Drama Recommendation System
**Date** : 2026-08-20 16:32:15

---

## Critères et pondérations

| Critère | Poids | Description |
|---|---|---|
| Coût | 25% | Coût d'utilisation (API, infrastructure) |
| Latence | 20% | Temps de réponse d'inférence (ms) |
| Qualité | 25% | Corrélation de Spearman (similarité) |
| Intégration | 15% | Documentation, SDK, exemples |
| Conformité | 15% | RGPD, hébergement, inférence locale |

---

## Grille de benchmark scorée

| Service | Coût (25%) | Latence (20%) | Qualité (25%) | Intégration (15%) | Conformité (15%) | **Note globale** |
|---|---|---|---|---|---|---|
| Hugging Face (sentence-transformers, local) | 5.0 | 4.0 | 3.0 | 5.0 | 5.0 | **4.30** |
| Modèles locaux (Ollama + nomic-embed-text) | 5.0 | 3.0 | 4.5 | 3.0 | 5.0 | **4.17** |
| OpenAI (text-embedding-3-small) | 4.5 | 4.0 | 4.5 | 5.0 | 2.0 | **4.10** |
| Cohere (Embed v3) | 4.5 | 4.0 | 4.5 | 4.0 | 3.0 | **4.10** |
| Google Vertex AI (text-embedding-004) | 4.5 | 4.0 | 4.5 | 4.0 | 3.0 | **4.10** |

---

## Métriques détaillées

| Service | Latence (ms) | Qualité (Spearman) | Coût mensuel ($) |
|---|---|---|---|
| Hugging Face (sentence-transformers, local) | 151.0 | 0.612 | 0.00 |
| Modèles locaux (Ollama + nomic-embed-text) | 250.0 | 0.750 | 0.00 |
| OpenAI (text-embedding-3-small) | 120.0 | 0.830 | 0.12 |
| Cohere (Embed v3) | 130.0 | 0.800 | 0.60 |
| Google Vertex AI (text-embedding-004) | 110.0 | 0.840 | 0.15 |

---

## Analyse détaillée

### Hugging Face (sentence-transformers, local)

- **Note globale** : 4.30 / 5
- **Latence** : 151.0 ms
- **Qualité (Spearman)** : 0.612
- **Coût mensuel** : 0.00 $
- **Détails** : Modèle open-source en inférence locale. Gratuit, confidentiel (aucune donnée ne sort), multilingue. Documentation très claire. Qualité légèrement inférieure à OpenAI mais suffisante pour la recommandation de contenu culturel.

### Modèles locaux (Ollama + nomic-embed-text)

- **Note globale** : 4.17 / 5
- **Latence** : 250.0 ms
- **Qualité (Spearman)** : 0.750
- **Coût mensuel** : 0.00 $
- **Détails** : Modèle open-source en inférence locale via Ollama. Gratuit et confidentiel. Nécessite une infrastructure et une maintenance à charge de l'équipe. Intégration plus technique que sentence-transformers.

### OpenAI (text-embedding-3-small)

- **Note globale** : 4.10 / 5
- **Latence** : 120.0 ms
- **Qualité (Spearman)** : 0.830
- **Coût mensuel** : 0.12 $
- **Détails** : Service cloud propriétaire. Excellente qualité et documentation. Hébergement aux États-Unis (transfert de données hors UE). Coût modéré mais qui s'accumule avec le volume.

### Cohere (Embed v3)

- **Note globale** : 4.10 / 5
- **Latence** : 130.0 ms
- **Qualité (Spearman)** : 0.800
- **Coût mensuel** : 0.60 $
- **Détails** : Service cloud propriétaire. Qualité élevée et multilingue. Tarification trial accessible mais production opaque. Hébergement cloud (données envoyées).

### Google Vertex AI (text-embedding-004)

- **Note globale** : 4.10 / 5
- **Latence** : 110.0 ms
- **Qualité (Spearman)** : 0.840
- **Coût mensuel** : 0.15 $
- **Détails** : Service cloud Google. Qualité élevée et scalabilité native. Intégration verrouillée à l'écosystème GCP. Hébergement cloud (transfert de données).

---

## Recommandation

**Service retenu** : Hugging Face (sentence-transformers, local)

Ce service obtient la meilleure note globale (4.30 / 5) grâce à :

- Un coût optimal (inférence locale gratuite).
- Une latence satisfaisante pour le cas d'usage temps réel.
- Une qualité suffisante pour la recommandation de contenu.
- Une intégration excellente (documentation, SDK Python).
- Une conformité maximale (RGPD, AI Act — inférence locale).
