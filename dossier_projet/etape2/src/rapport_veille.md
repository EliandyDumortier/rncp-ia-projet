# Bulletin de veille vérifié

**Collecte et validation** : 3 septembre 2026

**Articles/signaux retenus** : 10 sources officielles

**Périmètre** : service d'embeddings et règles applicables au projet K-Drama

Ce bulletin est une photographie initiale. Il ne prétend pas représenter plusieurs mois de collecte. Les éléments communautaires non recoupés et les faux positifs issus du mot « AI » dans « CIA » ont été retirés.

## Modèles et services

### `all-MiniLM-L6-v2`

- Source : [fiche officielle Hugging Face](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- Information retenue : 384 dimensions, licence Apache-2.0, langue déclarée English, troncature après 256 *word pieces*.
- Impact : modèle maintenu pour le POC anglophone; test multilingue nécessaire avant toute promesse en français.

### OpenAI `text-embedding-3-small`

- Source : [fiche officielle OpenAI](https://developers.openai.com/api/docs/models/text-embedding-3-small)
- Information retenue : 0,02 USD par million de tokens d'entrée.
- Impact : coût API de 0,12 USD pour l'hypothèse documentée de six millions de tokens.

### Google Vertex AI `gemini-embedding-001`

- Sources : [tarification Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/pricing) et [cycle de vie des modèles](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions)
- Information retenue : modèle stable, 0,00015 USD par 1 000 tokens en ligne.
- Impact : coût API de 0,90 USD pour la même hypothèse; le benchmark utilise le modèle actuel au lieu de figer son analyse sur `text-embedding-004`.

### Cohere Embed

- Sources : [tarification Cohere](https://cohere.com/pricing) et [politique trial](https://docs.cohere.com/docs/how-does-cohere-pricing-work)
- Information retenue : usage trial gratuit mais limité; pas de prix API Embed par token directement comparable sur la page publique consultée. Model Vault Embed 4 commence à 4 USD/heure ou 2 500 USD/mois.
- Impact : aucun faux coût mensuel n'est attribué; une offre de production nécessite une vérification commerciale.

## Réglementation

### Calendrier du règlement européen sur l'IA

- Sources : [Commission européenne](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) et [règlement sur EUR-Lex](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)
- Information retenue : entrée en vigueur le 1er août 2024; premières règles le 2 février 2025; règles générales et de transparence applicables depuis le 2 août 2026 selon le calendrier consulté.
- Impact : le projet conserve une information claire sur la recommandation algorithmique, mais ne présente plus l'article 50 comme une obligation spécifique d'offrir un mode non personnalisé.

### Profilage et RGPD

- Sources : [CNIL — profilage](https://www.cnil.fr/fr/profilage-et-decision-entierement-automatisee) et [CNIL — développement des systèmes d'IA](https://www.cnil.fr/fr/developpement-des-systemes-dia-les-recommandations-de-la-cnil-pour-respecter-le-rgpd)
- Information retenue : finalité déterminée, minimisation, transparence, protection dès la conception et maîtrise des risques liés aux profils inexacts ou enfermants.
- Impact : préférences et historique doivent être modifiables/supprimables et chaque finalité doit avoir une base légale documentée.

## Décisions prises

1. conserver `all-MiniLM-L6-v2` comme composant local du POC;
2. corriger sa description : anglais, et non multilingue;
3. retirer les chiffres de latence et de qualité non mesurés;
4. dater tous les prix et expliciter l'unité de calcul;
5. traiter le coût local comme un TCO à mesurer, pas comme zéro;
6. commencer un journal hebdomadaire de preuve.
