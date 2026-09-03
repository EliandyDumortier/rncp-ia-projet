# Synthèse de veille technique et réglementaire

**Projet** : K-Drama Recommendation System

**Revue documentée** : 3 septembre 2026

**Périmètre** : embeddings, services d'IA, recommandation personnalisée, RGPD et règlement européen sur l'IA

## 1. Statut de la preuve

Cette synthèse remplace une version qui annonçait trois mois, 324 articles et des tendances sans journal permettant de les vérifier. Ces chiffres sont retirés. La preuve disponible est une revue initiale datée, un agrégateur RSS exécutable et un journal de suivi qui commence le 3 septembre 2026.

La récurrence hebdomadaire ne peut être démontrée qu'au fil du temps. Le dispositif est planifié pour **une heure chaque vendredi** : 15 minutes de collecte, 30 minutes de lecture et recoupement, puis 15 minutes de rédaction et partage. Chaque exécution et chaque communication doivent être ajoutées à `journal_veille.md`; une intention ou un script ne vaut pas preuve de récurrence.

## 2. Besoin de veille

Le projet recommande des séries à partir de synopsis, genres, acteurs, préférences et historique. La veille doit donc répondre à quatre questions concrètes :

1. le service d'embeddings retenu reste-t-il disponible et adapté aux langues traitées ?
2. son prix et ses prérequis restent-ils compatibles avec un POC étudiant puis un déploiement limité ?
3. les choix de personnalisation respectent-ils les règles applicables aux données personnelles et au profilage ?
4. une alternative apporte-t-elle un gain démontrable sans coût, dépendance ou empreinte disproportionnés ?

## 3. Méthode et fiabilité des sources

Les sources officielles et primaires sont prioritaires. Les publications communautaires servent à découvrir un sujet, jamais à valider seules une règle, un tarif ou une capacité. Une information commerciale publiée par un fournisseur est fiable pour son propre prix ou contrat, mais son intérêt commercial est signalé et ses affirmations de performance doivent être recoupées ou mesurées.

| Source | Auteur et expertise | Intérêt possible | Fraîcheur vérifiée | Usage dans le projet |
|---|---|---|---|---|
| Commission européenne / EUR-Lex | Institution et texte juridique officiel | Aucun intérêt commercial | consultation 2026-09-03 | calendrier et portée du règlement IA |
| CNIL | Autorité française de protection des données | Aucun intérêt commercial | consultation 2026-09-03 | RGPD, profilage, privacy by design |
| Fiche Hugging Face du modèle | éditeur/mainteneurs du modèle | promotion de l'écosystème | consultation 2026-09-03 | licence, langue, dimensions, limites |
| Pages OpenAI, Google Cloud et Cohere | fournisseurs des services | intérêt commercial direct | consultation 2026-09-03 | prix et prérequis contractuels uniquement |
| Blogs, forums, Hacker News, Reddit | auteurs variables | variable | à vérifier par article | signaux faibles à confirmer par une source primaire |

Critères de validation d'une information : auteur identifiable, compétence sur le sujet, date disponible, document structuré, URL accessible, cohérence avec une seconde source de confiance lorsque le sujet l'exige et reformulation claire sans extrapolation.

## 4. Résultats techniques

### 4.1 `all-MiniLM-L6-v2` convient au POC anglophone, pas à une promesse multilingue

La fiche officielle indique 384 dimensions, une licence Apache-2.0, un modèle étiqueté **English** et une troncature des entrées supérieures à 256 *word pieces*. Un fichier de poids safetensors fait environ 90,9 Mo; il ne faut pas confondre ce fichier avec la taille totale de toutes les variantes du dépôt.

Conséquence : le choix local reste cohérent car les synopsis exploités sont majoritairement en anglais et le modèle est léger. En revanche, le dossier ne le décrit plus comme multilingue. La qualité des requêtes françaises doit être mesurée; si elle est insuffisante, un modèle multilingue devra être comparé sur un corpus K-Drama annoté.

### 4.2 Les prix ne sont comparables qu'avec la même unité

La charge de référence est de 6 millions de tokens : 10 000 synopsis indexés une fois, plus 1 000 requêtes par jour pendant 30 jours, avec l'hypothèse explicite de 150 tokens par texte.

- OpenAI `text-embedding-3-small` : 0,02 USD par million de tokens, donc **0,12 USD** pour cette hypothèse.
- Google `gemini-embedding-001` : 0,00015 USD par 1 000 tokens en ligne, soit 0,15 USD par million et **0,90 USD** pour cette hypothèse.
- Cohere : la clé trial est annoncée gratuite mais limitée. La page publique consultée ne donne pas de prix API Embed par token directement comparable; Model Vault Embed 4 commence à 4 USD/heure ou 2 500 USD/mois. Le dossier indique donc « non comparable » au lieu d'inventer 0,10 USD/million.
- Modèle local : pas de coût par appel ni de licence payante, mais l'hébergement, la mémoire, l'électricité, la supervision et la maintenance ont un coût. La valeur « 0 USD total » est supprimée.

Les prix sont une photographie au 3 septembre 2026 et doivent être revérifiés avant toute décision d'achat.

### 4.3 Les anciennes métriques de performance n'étaient pas recevables

Les latences cloud de 110 à 130 ms et les corrélations de Spearman attribuées aux fournisseurs n'avaient ni exécution, ni corpus commun, ni journal brut. Elles sont retirées. Le petit jeu de dix paires annotées à la main peut servir de test exploratoire local, mais pas de preuve de supériorité face à des benchmarks publiés sur d'autres données.

Protocole requis pour une future comparaison de performance : même corpus gelé, mêmes requêtes et annotations, même métrique, même région réseau, échauffement documenté, au moins 30 répétitions et conservation des résultats bruts.

### 4.4 Décision technique

Le POC conserve Sentence Transformers avec `all-MiniLM-L6-v2` en local : intégration Python simple, faible volume du modèle et maîtrise des textes envoyés. OpenAI est l'alternative SaaS au tarif publié le plus faible parmi les services chiffrables ici. Google est disponible mais plus cher avec l'unité retenue. Cohere reste intéressant fonctionnellement, mais sa production n'est pas chiffrée sans devis ou page tarifaire comparable.

La grille complète, les services non étudiés, les avantages, limites et prérequis sont dans `rapport_benchmark.md`.

## 5. Résultats réglementaires

### 5.1 Règlement européen sur l'IA

Le règlement (UE) 2024/1689 est entré en vigueur le 1er août 2024. Les interdictions et l'obligation de maîtrise de l'IA s'appliquent depuis le 2 février 2025; l'essentiel du règlement et les règles de transparence concernées s'appliquent depuis le 2 août 2026 selon le calendrier de la Commission.

L'article 50 vise notamment les systèmes qui interagissent directement avec une personne, la génération de contenu synthétique, la reconnaissance des émotions, la catégorisation biométrique et les hypertrucages. Il ne permet pas d'affirmer automatiquement que tout moteur de recommandation culturel est un système « à risque limité » ni qu'il impose une option non personnalisée. L'interface peut néanmoins annoncer l'usage d'une recommandation algorithmique comme mesure de transparence et de confiance.

À ce stade, le moteur K-Drama ne correspond pas aux cas à haut risque de l'annexe III identifiés dans le projet. Cette qualification est une analyse de contexte, pas une certification juridique; elle doit être revue si la finalité ou les données changent.

### 5.2 RGPD et profilage

Les préférences et l'historique rattachés à un compte sont des données personnelles. Leur traitement pour personnaliser les recommandations relève du profilage au sens large. La CNIL rappelle les risques de prédictions inexactes, de stéréotypes et d'enfermement dans les choix; elle insiste aussi sur la transparence, la finalité, la minimisation et la protection dès la conception.

Décisions projet : limiter les données aux préférences utiles, expliquer l'origine générale d'une recommandation, permettre la modification/suppression de l'historique et documenter la base légale. Le consentement n'est pas automatiquement l'unique base légale de tout traitement; il faut choisir et documenter la base adaptée à chaque finalité. Le consentement marketing reste distinct et facultatif.

### 5.3 Hors périmètre retiré

La PIPA sud-coréenne n'est pas retenue comme exigence principale : le fait que le catalogue contienne des œuvres coréennes ne signifie pas que le service traite des personnes en Corée. Elle devra être réévaluée seulement si le ciblage, l'établissement du responsable ou les traitements entrent dans son champ territorial.

## 6. Décisions et alertes de veille

| Signal | Seuil d'action | Action |
|---|---|---|
| retrait ou changement de licence du modèle | annonce officielle | geler la version, analyser la migration et tester l'alternative |
| hausse de coût SaaS | +20 % ou dépassement du budget projet | recalculer le TCO et présenter l'arbitrage |
| qualité française insuffisante | métrique sous le seuil défini en étape 3 | benchmarker un modèle multilingue sur le corpus gelé |
| changement RGPD/AI Act pertinent | texte ou ligne directrice applicable | ouvrir une tâche conformité et mettre à jour l'information utilisateur |
| flux indisponible | trois échecs hebdomadaires consécutifs | remplacer le flux par une source officielle équivalente |

## 7. Communication accessible

La synthèse utilise des titres hiérarchiques, des phrases courtes, des liens explicites et des tableaux simples. Elle est versionnée dans Git et destinée au responsable projet, aux développeurs et au jury. Les décisions doivent être communiquées dans la pull request de l'étape 2; la date et le destinataire sont ensuite inscrits dans `journal_veille.md`.

## 8. Sources principales

- [Commission européenne — cadre réglementaire sur l'IA](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) — consulté le 2026-09-03.
- [EUR-Lex — règlement (UE) 2024/1689, article 50](https://eur-lex.europa.eu/eli/reg/2024/1689/oj) — consulté le 2026-09-03.
- [CNIL — profilage et décision entièrement automatisée](https://www.cnil.fr/fr/profilage-et-decision-entierement-automatisee) — consulté le 2026-09-03.
- [CNIL — recommandations RGPD pour le développement des systèmes d'IA](https://www.cnil.fr/fr/developpement-des-systemes-dia-les-recommandations-de-la-cnil-pour-respecter-le-rgpd) — consulté le 2026-09-03.
- [Hugging Face — fiche `all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) — consulté le 2026-09-03.
- [OpenAI — `text-embedding-3-small`](https://developers.openai.com/api/docs/models/text-embedding-3-small) — consulté le 2026-09-03.
- [Google Cloud — tarification Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/pricing) — consulté le 2026-09-03.
- [Google Cloud — versions des modèles Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions) — consulté le 2026-09-03.
- [Cohere — tarification](https://cohere.com/pricing) et [fonctionnement du trial](https://docs.cohere.com/docs/how-does-cohere-pricing-work) — consultés le 2026-09-03.

## 9. Limite actuelle à présenter honnêtement au jury

Le dispositif technique et la première synthèse sont opérationnels. En revanche, plusieurs semaines de veille récurrente et plusieurs communications successives ne peuvent pas être rétroactivement prouvées. Les prochaines entrées du journal constitueront cette preuve temporelle.
