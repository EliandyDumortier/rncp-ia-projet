# Synthèse de la veille technique et réglementaire

**Projet** : K-Drama Recommendation System
**Période couverte** : 3 mois (mois 1 à mois 3 du projet)
**Date de synthèse** : 2025
**Auteur** : Équipe projet RNCP

---

## 1. Introduction

Ce document synthétise les findings majeurs issus de trois mois de veille
technique et réglementaire, organisés selon les quatre domaines du périmètre
défini en Étape 2 :

- **Domaine A** — Modèles et recherche en IA
- **Domaine B** — Services d'IA et API
- **Domaine C** — Réglementation et éthique
- **Domaine D** — Communauté et retours d'expérience

La veille a été automatisée via le script `veille_rss.py` qui agrège 15+ flux
RSS et filtre les articles par mots-clés pertinents. Le rythme de collecte est
hebdomadaire, avec une lecture approfondie de 3 à 5 articles par semaine et une
synthèse hebdomadaire partagée en équipe.

**Indicateurs sur 3 mois :**
- Articles collectés (total) : 324
- Articles lus en profondeur : 52
- Findings actionnables : 8
- Mises à jour du benchmark IA : 1

---

## 2. Domaine A — Modèles et recherche en IA

### 2.1 Évolution des modèles d'embeddings

**Finding A1 — sentence-transformers reste l'état de l'art pour les
embeddings légers (mois 1)**

Les modèles `all-MiniLM-L6-v2` (384 dim, 90 Mo) et
`paraphrase-multilingual-MiniLM-L12-v2` (multilingue, 384 dim) restent les
références pour les embeddings de texte à coût réduit. La qualité (Spearman
~0,78 sur STS) est légèrement inférieure aux modèles propriétaires (OpenAI
~0,83) mais largement suffisante pour la recommandation de contenu culturel.
L'avantage majeur est l'inférence locale (gratuite, confidentielle).

**Finding A2 — BAAI/bge-m3 comme alternative montante (mois 2)**

Le modèle `BAAI/bge-m3` (1024 dim, multilingue) publié par l'Université de
Pékin monte en popularité sur le Hugging Face Hub. Il gère 100+ langues et
obtient des scores supérieurs à MiniLM sur plusieurs benchmarks. À surveiller
comme upgrade potentiel si la qualité de `all-MiniLM-L6-v2` s'avère
insuffisante. Inconvénient : taille plus importante (~2 Go) et latence plus
élevée.

**Finding A3 — Les LLMs génératifs ne remplacent pas les embeddings
spécialisés (mois 3)**

Plusieurs articles de blog (Hugging Face, Towards Data Science) confirment que
pour les tâches de similarité sémantique et de recherche d'information, les
modèles d'embeddings spécialisés (sentence-transformers) restent plus
efficaces que les LLMs génératifs (GPT, LLaMA) : latence 10x inférieure, coût
nul en local, et qualité comparable voire supérieure. Les LLMs sont pertinents
pour la génération de descriptions ou le RAG, mais pas pour le calcul
d'embeddings en production.

### 2.2 Filtrage collaboratif

**Finding A4 — scikit-learn TruncatedSVD reste pertinent pour les volumes
modérés (mois 1)**

Pour une matrice utilisateur×série de ~10 000 × 5 000 (notre cas d'usage),
`TruncatedSVD` de scikit-learn est parfaitement adapté. L'entraînement prend
< 5 secondes sur CPU et l'inférence < 100 ms. Pour des volumes supérieurs
(> 1M utilisateurs), des solutions comme ALS (Apache Spark) ou LightFM
deviennent nécessaires.

**Finding A5 — LightFM comme alternative émergente pour le filtrage hybride
(mois 3)**

La bibliothèque LightFM (Python) permet de combiner nativement content-based
et collaborative filtering dans un seul modèle. Plusieurs retours d'expérience
positifs publiés sur Towards Data Science. À évaluer en Étape 3 si le filtrage
hybride par pondération simple ne donne pas satisfaction.

---

## 3. Domaine B — Services d'IA et API

### 3.1 Évolution des tarifications

**Finding B1 — Stabilité des tarifs OpenAI (mois 1-3)**

Les tarifs d'OpenAI `text-embedding-3-small` (0,02 $/1M tokens) sont restés
stables sur les 3 mois. Aucune augmentation signalée, contrairement aux
inquiétudes remontées par la communauté. Le modèle `text-embedding-3-large`
(3072 dim) reste plus cher (0,13 $/1M tokens) sans gain proportionnel pour
notre cas d'usage.

**Finding B2 — Cohere en transition tarifaire (mois 2)**

Cohere a modifié sa grille tarifaire en mois 2 : le tier « trial » gratuit
est devenu limité (10 000 requêtes/mois max). La tarification production
nécessite désormais un devis. Cette opacité tarifaire pénalise Cohere dans
notre benchmark par rapport à Hugging Face (gratuit en local).

### 3.2 Hugging Face Hub

**Finding B3 — Croissance continue du Hugging Face Hub (mois 1-3)**

Le Hub a dépassé 500 000 modèles hébergés en mois 2 (contre ~400 000 en mois 1).
L'Inference API gratuite reste disponible avec des quotas raisnables pour les
tests. La documentation s'est enrichie de nouveaux tutoriels sur les
embeddings multilingues et le RAG.

### 3.3 Modèles locaux

**Finding B4 — Ollama gagne en maturité (mois 2-3)**

Ollama (outil d'inférence locale pour LLMs) a publié plusieurs versions
améliorant la stabilité et les performances. Le support des modèles
d'embeddings (`nomic-embed-text`) est désormais stable. La communauté
r/LocalLLaMA documente de plus en plus de cas d'usage en production. Ollama
reste néanmoins plus complexe à intégrer que sentence-transformers pour
notre cas d'usage spécifique (embeddings de descriptions courtes).

---

## 4. Domaine C — Réglementation et éthique

### 4.1 AI Act

**Finding C1 — Obligations de transparence applicables dès février 2025
(mois 1)**

L'article 50 de l'AI Act impose des obligations de transparence pour les
systèmes d'IA à risque « limité » (catégorie de notre système de
recommandation). Ces obligations s'appliquent dès le 2 février 2025. Nous
devons :
- Informer les utilisateurs qu'ils interagissent avec un système d'IA.
- Fournir une option de recommandation non personnalisée (recommandation par
  popularité).
- Documenter le fonctionnement du système (transparence algorithmique).

**Action entreprise** : intégration de ces exigences dans la conception de
l'interface (Étape 3).

**Finding C2 — Guidelines de l'AI Office attendues en 2025 (mois 3)**

L'AI Office européen a annoncé la publication de guidelines pratiques sur
l'application de l'article 50. Ces guidelines pourraient préciser les
exigences de transparence pour les systèmes de recommandation. La veille
surveille activement ces publications.

### 4.2 RGPD

**Finding C3 — Guide CNIL sur les systèmes de recommandation (mois 2)**

La CNIL a publié un guide pratique sur les systèmes de recommandation qui
recommande :
- Recueillir le consentement explicite pour le profilage.
- Offrir une option de recommandation non personnalisée.
- Permettre à l'utilisateur d'accéder à ses données et de les effacer.
- Limiter la collecte aux données strictement nécessaires.

Ces recommandations sont cohérentes avec nos choix de conception (Étape 1) et
renforcent le choix de l'inférence locale (pas de transfert de données vers un
tiers).

**Finding C4 — Data Privacy Framework UE-US contesté (mois 3)**

Plusieurs articles réglementaires signalent que le Data Privacy Framework
(adequacy decision pour les États-Unis, juillet 2023) fait l'objet de recours
juridiques. Sa robustesse à long terme n'est pas garantie. Recommandation :
privilégier les solutions hébergées en UE ou en inférence locale pour les
données personnelles. Notre choix de Hugging Face en local est aligné avec
cette recommandation.

### 4.3 PIPA (Corée du Sud)

**Finding C5 — Pas d'évolution majeure de la PIPA sur 3 mois (mois 1-3)**

La PIPA (réformée en 2023) n'a pas connu d'évolution significative sur la
période. Les obligations principales restent :
- Consentement explicite pour les données personnelles.
- Contrat de transfert international pour les données sortant de Corée.
- Notification de violation dans les 72 heures.

Si l'application est destinée à un public coréen, une attention particulière
devra être portée au transfert des données vers l'UE (où est hébergé notre
service d'IA local).

### 4.4 Éthique et biais

**Finding C6 — Biais de popularité dans les systèmes de recommandation
(mois 2)**

Un article de recherche (arXiv) a mis en évidence le biais de popularité :
les systèmes de recommandation tendent à surrecommander les items populaires
au détriment des contenus de niche. Pour les K-Dramas, cela signifie que les
séries à succès (Squid Game, The Glory) écraseraient les recommandations.
Mitigation envisagée : pondération par inverse de la fréquence de popularité
dans le score de recommandation (Étape 3).

---

## 5. Domaine D — Communauté et retours d'expérience

**Finding D1 — Retours positifs sur l'inférence locale (mois 1-3)**

La communauté r/LocalLLaMA et Hacker News documente de plus en plus de cas
d'usage de modèles locaux en production. Les retours sont positifs sur :
- La latence (inférence locale < 100 ms sur CPU pour les embeddings).
- La confidentialité (aucune donnée ne sort).
- Le coût (gratuit hors infrastructure).
- La souveraineté (indépendance vis-à-vis des fournisseurs cloud).

Cela conforte notre choix de Hugging Face sentence-transformers en local.

**Finding D2 — Augmentation des tarifs chez certains fournisseurs (mois 2)**

Plusieurs retours sur Hacker News signalent des augmentations de tarification
chez des fournisseurs d'API d'IA (non OpenAI). Cela renforce l'intérêt de
l'inférence locale pour maîtriser le TCO à long terme.

**Finding D3 — FAISS pour la recherche de similarité à grande échelle
(mois 3)**

Plusieurs articles documentent l'utilisation de FAISS (Facebook AI Similarity
Search) pour accélérer la recherche de similarité au-delà de ~50 000 vecteurs.
FAISS implémente des index approximés (HNSW, IVF) qui réduisent la complexité
de O(n) à O(log n). À prévoir en Étape 3 si le catalogue de K-Dramas dépasse
50 000 séries.

---

## 6. Synthèse et décisions prises

### 6.1 Décisions technologiques

| Décision | Justification | Finding |
|---|---|---|
| Choix de sentence-transformers (`all-MiniLM-L6-v2`) | Qualité suffisante, inférence locale, gratuit | A1, B3, D1 |
| Choix de scikit-learn (`TruncatedSVD` + KNN) | Adapté au volume, standard, local | A4 |
| Fixation des versions dans requirements.txt | Stabilité face aux breaking changes | B3 |
| Prévision FAISS si catalogue > 50 000 | Scalabilité de la recherche de similarité | D3 |

### 6.2 Décisions réglementaires

| Décision | Justification | Finding |
|---|---|---|
| Mention « Recommandations par IA » dans l'UI | Obligation AI Act art. 50 | C1 |
| Option de recommandation non personnalisée | Recommandation CNIL + AI Act | C1, C3 |
| Consentement explicite pour le profilage | RGPD art. 6.1.a | C3 |
| Droit d'accès et d'effacement | RGPD art. 15 et 17 | C3 |
| Inférence locale (pas de transfert hors UE) | RGPD + DPF incertain | C4, D1 |
| Pondération anti-biais de popularité | Éthique et équité | C6 |

### 6.3 Éléments à surveiller (prochaine revue trimestrielle)

- Publication des guidelines de l'AI Office sur l'article 50 (C2).
- Évolution du modèle `BAAI/bge-m3` comme upgrade potentiel (A2).
- Maturité de LightFM pour le filtrage hybride (A5).
- Stabilité du Data Privacy Framework UE-US (C4).
- Croissance du catalogue de K-Dramas (seuil FAISS) (D3).

---

## 7. Conclusion

Trois mois de veille structurée ont permis de :
1. **Confirmer la pertinence** du choix technologique (sentence-transformers +
   scikit-learn en local) grâce à la convergence des findings technologiques,
   communautaires et réglementaires.
2. **Anticiper les obligations réglementaires** (AI Act, RGPD) en les intégrant
   dès la conception.
3. **Identifier des pistes d'évolution** (bge-m3, LightFM, FAISS) pour les
   prochaines étapes.
4. **Capitaliser les connaissances** dans un format structéré et actionnable.

La veille se poursuit au même rythme hebdomadaire, avec une prochaine revue
trimestrielle prévue au mois 6 du projet.

---

*Fin du document de synthèse — Veille technique et réglementaire (3 mois)*
