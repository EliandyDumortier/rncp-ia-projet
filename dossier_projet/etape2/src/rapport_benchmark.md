# Benchmark des services d'embeddings

**Date de revue des informations** : 2026-09-03

## Besoin et contraintes

Le service doit représenter des synopsis de K-Dramas pour une recommandation hybride, s'intégrer à Python/FastAPI, fonctionner sur CPU pour le POC, limiter les transferts de données et rester exploitable avec un budget étudiant. Les synopsis sont principalement en anglais; les préférences et requêtes peuvent être multilingues.

## Méthode et limites

Cette grille est une **matrice de décision**, pas un classement scientifique. Chaque note va de 1 (défavorable) à 5 (favorable). Pondération: fonctionnel 30 %, gouvernance des données 25 %, prévisibilité du coût 15 %, intégration 15 %, sobriété d'exploitation 15 %. Aucune latence ou qualité cloud n'est inventée: elles restent non mesurées tant que tous les candidats n'ont pas été exécutés avec le même corpus, la même région et le même protocole.

Hypothèse de coût API: 6 000 000 tokens (10 000 textes initiaux + 1 000 requêtes/jour pendant 30 jours, 150 tokens/texte). Coûts hors taxes, stockage, réseau, hébergement et travail humain.

## Grille de décision

| Service | Fonctionnel 30 % | Données 25 % | Coût 15 % | Intégration 15 % | Sobriété 15 % | Total / 5 | API pour l'hypothèse |
|---|---:|---:|---:|---:|---:|---:|---:|
| Sentence Transformers — all-MiniLM-L6-v2 (local) | 4 | 5 | 4 | 5 | 4 | **4.40** | non comparable |
| OpenAI — text-embedding-3-small (API) | 5 | 3 | 5 | 5 | 2 | **4.05** | 0.12 USD |
| Ollama — nomic-embed-text (local) | 4 | 5 | 3 | 3 | 3 | **3.80** | non comparable |
| Google Vertex AI — gemini-embedding-001 (API) | 5 | 3 | 4 | 3 | 2 | **3.60** | 0.90 USD |
| Cohere — Embed (API / Model Vault) | 5 | 3 | 2 | 4 | 2 | **3.45** | non comparable |

## Analyse par candidat

### Sentence Transformers — all-MiniLM-L6-v2 (local)

- Prix/TCO : Licence Apache-2.0 et aucun coût API; hébergement, électricité et maintenance ne sont pas gratuits.
- Prérequis : Python, PyTorch, sentence-transformers, environ 91 Mo pour un fichier de poids; synopsis principalement en anglais.
- Avantages : Inférence maîtrisée, 384 dimensions, intégration Python simple, aucun envoi des textes à un fournisseur d'embeddings.
- Limites : Fiche officielle étiquetée English; entrées tronquées au-delà de 256 word pieces; capacité et latence dépendent de l'hôte.

### OpenAI — text-embedding-3-small (API)

- Prix/TCO : 0,02 USD par million de tokens d'entrée, relevé sur la fiche officielle.
- Prérequis : Compte, clé API, réseau, budget et revue contractuelle/RGPD du sous-traitant.
- Avantages : Multilingue, API documentée, coût variable faible pour le volume de référence.
- Limites : Dépendance réseau et fournisseur; textes transmis à un tiers; impact par requête non publié de façon comparable.

### Google Vertex AI — gemini-embedding-001 (API)

- Prix/TCO : 0,00015 USD par 1 000 tokens en ligne, soit 0,15 USD par million, relevé sur Vertex AI Pricing.
- Prérequis : Projet Google Cloud, facturation, IAM, SDK/API Vertex AI et région disponible.
- Avantages : Modèle stable actuel, multilingue, service géré et scalable.
- Limites : Dépendance GCP; 3 072 dimensions par défaut donc stockage supérieur; gouvernance contractuelle à instruire.

### Cohere — Embed (API / Model Vault)

- Prix/TCO : Clé trial gratuite mais limitée; aucun prix API Embed par token comparable sur la page consultée. Model Vault Embed 4 démarre à 4 USD/heure ou 2 500 USD/mois.
- Prérequis : Compte, clé de production ou contrat Model Vault, réseau et revue contractuelle/RGPD.
- Avantages : Embeddings multilingues et options de déploiement entreprise.
- Limites : Coût de production API non comparable depuis les informations publiques consultées; solution surdimensionnée pour ce POC.

### Ollama — nomic-embed-text (local)

- Prix/TCO : Aucun coût API, mais coût réel de machine, énergie et exploitation.
- Prérequis : Service Ollama séparé, téléchargement et cycle de vie du modèle, RAM/disque supplémentaires.
- Avantages : Exécution locale et isolation des textes.
- Limites : Composant d'exploitation supplémentaire sans bénéfice démontré sur le corpus du POC.
- Décision : Non retenu: complexité supérieure à sentence-transformers sans gain mesuré avec le protocole du projet.

## Services identifiés mais non étudiés en détail

- **AWS Bedrock embeddings** — Écarté du détail: un nouvel écosystème cloud n'apporte pas de besoin fonctionnel non couvert.
- **Voyage AI** — Écarté faute de temps pour exécuter un protocole identique et de besoin non couvert par les candidats étudiés.
- **Modèles génératifs généralistes** — Écartés: générer du texte est disproportionné pour calculer une similarité de synopsis.

## Conclusion

**Service retenu pour le POC : Sentence Transformers avec `all-MiniLM-L6-v2`, en local.** Il répond au besoin sur les synopsis anglophones, réduit la dépendance à une API externe et son faible volume facilite le déploiement CPU. Ce choix ne signifie ni coût total nul, ni conformité automatique, ni supériorité absolue. Son risque principal est la qualité sur les requêtes non anglaises; une évolution vers un modèle multilingue devra être testée sur un jeu annoté représentatif.

OpenAI reste l'alternative SaaS la moins chère parmi les coûts API publiés et comparables ici. Google est 7,5 fois plus cher sur l'unité token retenue (0,15 contre 0,02 USD/million); Cohere n'est pas chiffré artificiellement lorsque le tarif public comparable manque.

## Sources officielles

- [OpenAI model pricing](https://developers.openai.com/api/docs/models/text-embedding-3-small) — consulté le 2026-09-03.
- [Cohere pricing](https://cohere.com/pricing) — consulté le 2026-09-03.
- [Cohere trial policy](https://docs.cohere.com/docs/how-does-cohere-pricing-work) — consulté le 2026-09-03.
- [Google Vertex AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing) — consulté le 2026-09-03.
- [Google model lifecycle](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions) — consulté le 2026-09-03.
- [all-MiniLM-L6-v2 model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) — consulté le 2026-09-03.
