# Étape 2 — Veille et sélection du service d'IA

Cette étape couvre C6 (veille), C7 (benchmark) et C8 (installation et configuration du service retenu) pour le système de recommandation K-Drama.

## Livrables et preuves

| Compétence | Preuve | Limite déclarée |
|---|---|---|
| C6 | `src/veille_rss.py`, `src/rapport_veille.md`, `src/synthese_veille.md`, `src/journal_veille.md` | la récurrence se démontre séance après séance; une seule séance est actuellement journalisée |
| C7 | `src/benchmark_ia.py`, `src/rapport_benchmark.md` | grille de décision documentée; les API cloud n'ont pas été exécutées dans un protocole de performance commun |
| C8 | `src/config_ia_service.py` et commandes ci-dessous | validation locale du composant retenu; l'API complète est réalisée en étape 3 |

La correspondance détaillée avec les 18 critères officiels et les deux preuves encore temporelles est disponible dans `VALIDATION_E2.md`.

Le précédent dossier annonçait des volumes de veille, performances et prix non justifiés. Ils ont été supprimés ou remplacés par des faits datés et sourcés.

## Besoin reformulé

Le projet doit recommander des K-Dramas à partir des synopsis, genres, acteurs, préférences et historiques. Le composant d'IA doit :

- représenter les synopsis pour calculer une similarité sémantique;
- s'intégrer à Python et à la future API FastAPI;
- fonctionner sur CPU dans le POC et respecter un budget étudiant;
- limiter l'exposition des données personnelles;
- rester testable, versionnable et remplaçable;
- éviter un service génératif disproportionné pour une tâche d'embeddings.

Les synopsis du catalogue sont principalement en anglais. Les requêtes utilisateur peuvent être françaises ou anglaises : cette différence est une limite à tester et non une capacité supposée.

## Structure

```text
etape2/
├── README.md
├── requirements.txt
├── src/
│   ├── benchmark_ia.py
│   ├── config_ia_service.py
│   ├── collecte_veille_rss.md  # créé lors d'une collecte
│   ├── journal_veille.md
│   ├── rapport_benchmark.md
│   ├── rapport_veille.md
│   ├── synthese_veille.md
│   └── veille_rss.py
└── tests/
    └── test_etape2.py
```

## Installation

Prérequis : Python 3.10 ou supérieur, `pip`, connexion internet pour les flux et le premier téléchargement du modèle.

Sous PowerShell :

```powershell
cd dossier_projet/etape2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Sous Linux ou macOS :

```bash
cd dossier_projet/etape2
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Le dossier `.venv` est ignoré par Git.

## Utilisation

### Veille C6

```powershell
python src/veille_rss.py
```

Le script agrège les flux, retire les doublons, filtre sur des mots complets et écrit la collecte brute `src/collecte_veille_rss.md`. Il ne remplace jamais `src/rapport_veille.md`, qui contient uniquement des informations relues et confirmées. L'historique généré `src/veille_historique.json` évite de recompter les mêmes liens. Les résultats RSS restent des candidats : une information tarifaire ou juridique doit être confirmée dans une source officielle avant d'entrer dans la synthèse.

Après chaque séance réelle, compléter `src/journal_veille.md` avec la durée, les sources, la conclusion et le lien de communication. Le rythme cible est une heure par semaine.

### Benchmark C7

```powershell
python src/benchmark_ia.py
```

Le script régénère `src/rapport_benchmark.md` à partir des hypothèses, tarifs datés, prérequis et notes de décision versionnés dans le code. Il ne produit pas de fausses mesures de latence ou de qualité cloud.

### Configuration C8

```powershell
python src/config_ia_service.py
```

Le service retenu est Sentence Transformers avec `all-MiniLM-L6-v2`, complété par scikit-learn pour le prototype collaboratif. La fiche du modèle le déclare anglophone, produit des vecteurs de 384 dimensions et tronque les entrées longues. Le premier lancement télécharge les poids depuis Hugging Face; les exécutions suivantes utilisent le cache local.

Le script vérifie le chargement, l'indexation, la recommandation par similarité, l'entraînement SVD/KNN et plusieurs erreurs d'entrée. Aucun identifiant ou mot de passe n'est requis pour ce composant local. L'accès authentifié et l'exposition HTTP appartiennent à l'API de l'étape 3.

### Tests de non-régression légers

```powershell
python -m unittest discover -s tests -v
```

Ces tests vérifient le volume et les calculs de prix documentés, la présence des limites dans le rapport et le correctif qui empêche `ai` de correspondre à `CIA`.

## Données et interconnexions

Entrées du composant local : synopsis publics du catalogue et, pour la partie collaborative de démonstration, tuples utilisateur-série-note synthétiques. Sorties : vecteurs, similarités et identifiants ordonnés. Les mots de passe, e-mails et consentements ne sont pas nécessaires à l'inférence d'embeddings et ne doivent pas lui être transmis.

```text
catalogue de synopsis ──> all-MiniLM-L6-v2 ──> vecteurs ──> similarité cosine
notes utilisateur-série ────────────────────> SVD / KNN ──> candidats
```

En étape 3, ces briques sont intégrées à l'API du modèle. Le déploiement gratuit peut utiliser un repli TF-IDF en cas de contrainte mémoire; il s'agit d'une évolution d'exploitation documentée à l'étape 3, pas d'une modification rétroactive du choix de POC.

## Décision du benchmark

`all-MiniLM-L6-v2` local est retenu pour le POC : faible taille, intégration directe et absence d'appel à un fournisseur externe pour encoder les textes. OpenAI est l'alternative SaaS au coût public comparable le plus bas dans la revue du 3 septembre 2026. Google est chiffré avec son tarif token actuel. Cohere reste « non comparable » lorsque la page publique ne fournit pas de prix API Embed par token.

La licence ou l'absence de facturation par appel ne rend pas le local gratuit : machine, mémoire, énergie, hébergement et maintenance relèvent du coût total de possession.

## Conformité et accessibilité

Les préférences et historiques liés à un compte sont des données personnelles pouvant alimenter un profil. Le projet applique finalité, minimisation, transparence, modification et suppression. L'article 50 du règlement européen sur l'IA n'est plus présenté comme imposant automatiquement un mode non personnalisé à tout recommandeur.

Les documents emploient des titres hiérarchisés, des liens explicites, des tableaux simples et du texte lisible sans dépendre de la couleur. Lors de l'export en PDF, vérifier les signets, l'ordre de lecture, le contraste et le texte alternatif des éventuelles images.

## Sources de référence

- [Fiche officielle all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- [Tarif officiel OpenAI text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small)
- [Tarification Google Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/pricing)
- [Tarification Cohere](https://cohere.com/pricing)
- [Règlement européen sur l'IA sur EUR-Lex](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)
- [CNIL — profilage et décision automatisée](https://www.cnil.fr/fr/profilage-et-decision-entierement-automatisee)

Toutes les valeurs temporelles doivent être revérifiées avant soutenance ou décision d'achat.
