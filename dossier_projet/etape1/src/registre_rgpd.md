# Registre des traitements de données personnelles — RGPD (art. 30)

## Informations générales

| Champ | Valeur |
|---|---|
| **Nom du projet** | Système de recommandation de K-Dramas par IA |
| **Responsable de traitement** | Équipe Data — Projet académique RNCP |
| **Délégué à la protection des données (DPO)** | [À compléter] |
| **Date de création du registre** | 2025 |
| **Date de dernière mise à jour** | 2025 |
| **Base légale** | Consentement (RGPD art. 6.1.a) |
| **Finalité principale** | Recommandation personnalisée de K-Dramas aux utilisateurs enregistrés |

---

## Traitement n°1 — Inscription et authentification des utilisateurs

### Description

Ce traitement permet à un utilisateur de créer un compte, de s'authentifier et d'accéder à son profil sur le système de recommandation.

### Données traitées

| Catégorie de données | Données spécifiques | Source | Base légale |
|---|---|---|---|
| Identifiants | Pseudonyme | Saisie utilisateur | Consentement (art. 6.1.a) |
| Contact | Email (haché SHA-256) | Saisie utilisateur | Consentement (art. 6.1.a) |
| Authentification | Mot de passe (haché bcrypt) | Saisie utilisateur | Consentement (art. 6.1.a) |
| Consentement | Consentement collecte, consentement marketing, date et méthode | Formulaire d'inscription | Obligation légale (art. 7) |
| Métadonnées | Date d'inscription, date de dernière activité | Système automatique | Intérêt légitime (art. 6.1.f) |

### Mesures de sécurité

- **Hachage des emails** : SHA-256 via pgcrypto (aucun email stocké en clair).
- **Hachage des mots de passe** : bcrypt via passlib (jamais stocké en clair).
- **Authentification JWT** : tokens signés avec secret, expiration configurable.
- **Row Level Security (RLS)** : politiques PostgreSQL limitant l'accès aux données.
- **Journalisation** : table `journal_acces` enregistrant les accès aux données personnelles.

### Destinataires

| Destinataire | Accès | Finalité |
|---|---|---|
| Utilisateur lui-même | Lecture/écriture de son propre profil | Gestion de compte |
| Administrateurs | Lecture (vue anonymisée) | Administration et modération |
| Système (automatique) | Lecture/écriture | Authentification et gestion de session |

### Durée de conservation

| Donnée | Durée de conservation | Justification |
|---|---|---|
| Compte actif | Durée de vie du projet + 3 ans d'inactivité | Limite de conservation (art. 5.1.e) |
| Compte inactif | Suppression automatique après 3 ans d'inactivité | Fonction `purger_comptes_inactifs()` |
| Journal des accès | 1 an | Traçabilité et audit (art. 30) |

### Droits des personnes concernées

- **Droit d'accès** (art. 15) : endpoint `GET /api/v1/auth/me`.
- **Droit de rectification** (art. 16) : endpoint `PUT /api/v1/auth/me`.
- **Droit à l'effacement** (art. 17) : endpoint `DELETE /api/v1/auth/me` (anonymisation).
- **Droit à la portabilité** (art. 20) : endpoint `GET /api/v1/auth/me/export`.

---

## Traitement n°2 — Notes et avis des utilisateurs sur les K-Dramas

### Description

Ce traitement permet aux utilisateurs authentifiés d'attribuer des notes (1-10) et des avis textuels aux K-Dramas qu'ils ont visionnés. Ces données alimentent le moteur de recommandation.

### Données traitées

| Catégorie de données | Données spécifiques | Source | Base légale |
|---|---|---|---|
| Évaluation | Note (1-10) | Saisie utilisateur | Consentement (art. 6.1.a) |
| Opinion | Commentaire / avis textuel | Saisie utilisateur | Consentement (art. 6.1.a) |
| Métadonnées | Date de la note, date de modification | Système automatique | Intérêt légitime (art. 6.1.f) |
| Lien | Identifiant de l'utilisateur, identifiant du K-Drama | Système automatique | Intérêt légitime (art. 6.1.f) |

### Mesures de sécurité

- **Authentification requise** : seuls les utilisateurs connectés peuvent créer/modifier leurs notes.
- **Contrainte d'unicité** : un utilisateur ne peut noter qu'une seule fois un K-Drama (UNIQUE en base).
- **Validation des données** : Pydantic valide que la note est comprise entre 1 et 10.
- **Suppression en cascade** : les notes sont supprimées/anonymisées avec le compte utilisateur.

### Destinataires

| Destinataire | Accès | Finalité |
|---|---|---|
| Utilisateur lui-même | Lecture/écriture de ses propres notes | Gestion des notes |
| Autres utilisateurs | Lecture (note et commentaire) | Consultation publique |
| Système de recommandation | Lecture (note uniquement) | Calcul de recommandations |
| Administrateurs | Lecture/modération | Modération des contenus |

### Durée de conservation

| Donnée | Durée de conservation | Justification |
|---|---|---|
| Notes et avis | Durée de vie du projet | Nécessaire pour les recommandations |
| Notes d'un compte supprimé | Conservées mais anonymisées (lien utilisateur rompu) | Intégrité des statistiques |

---

## Traitement n°3 — Historique de visionnage

### Description

Ce traitement enregistre l'historique de visionnage des utilisateurs (quels K-Dramas ont été vus, à quel stade) pour affiner les recommandations.

### Données traitées

| Catégorie de données | Données spécifiques | Source | Base légale |
|---|---|---|---|
| Historique | K-Drama visionné, épisodes vus, statut (à voir, en cours, terminé, abandonné) | Saisie utilisateur / système | Consentement (art. 6.1.a) |
| Métadonnées | Date de début, date de fin, date de création | Système automatique | Intérêt légitime (art. 6.1.f) |

### Mesures de sécurité

- **Authentification requise** : seuls les utilisateurs connectés peuvent consulter et modifier leur historique.
- **Row Level Security** : un utilisateur ne peut voir que son propre historique.
- **Suppression en cascade** : l'historique est supprimé intégralement lors du droit à l'effacement.

### Destinataires

| Destinataire | Accès | Finalité |
|---|---|---|
| Utilisateur lui-même | Lecture/écriture de son propre historique | Suivi du visionnage |
| Système de recommandation | Lecture | Entraînement des modèles de recommandation |

### Durée de conservation

| Donnée | Durée de conservation | Justification |
|---|---|---|
| Historique de visionnage | Supprimé à l'effacement du compte ou après 2 ans d'inactivité | Minimisation (art. 5.1.c) |

---

## Traitement n°4 bis — Préférences de recommandation, favoris et retours d'intérêt

### Description

Ce traitement permet à un utilisateur authentifié d'améliorer la qualité des recommandations qui lui sont proposées (étape 3) en indiquant, de façon **entièrement optionnelle**, des acteurs/actrices favoris, des genres favoris, une préférence de fin heureuse, une liste de favoris, et un retour explicite d'intérêt ("je veux regarder" / "pas intéressé(e)") sur la fiche d'un K-Drama.

### Données traitées

| Catégorie de données | Données spécifiques | Source | Base légale | Caractère |
|---|---|---|---|---|
| Préférences de contenu | Genres favoris (maximum 3) | Saisie utilisateur (profil) | Consentement (art. 6.1.a) | **Optionnel** |
| Préférences de contenu | Acteurs/actrices favoris (maximum 5) | Saisie utilisateur (profil) | Consentement (art. 6.1.a) | **Optionnel** |
| Préférence de contenu | Fin heureuse uniquement (booléen) | Saisie utilisateur (profil) | Consentement (art. 6.1.a) | **Optionnel** |
| Favoris | Liste de K-Dramas ajoutés en favoris | Action utilisateur (fiche drama) | Consentement (art. 6.1.a) | **Optionnel** |
| Retour d'intérêt | "Je veux regarder" / "Pas intéressé(e)" par K-Drama | Action utilisateur (fiche drama) | Consentement (art. 6.1.a) | **Optionnel** |
| Métadonnées | Dates de création/modification | Système automatique | Intérêt légitime (art. 6.1.f) | Automatique |

Ces données ne modifient pas la finalité du traitement n°1 (inscription) : elles poursuivent la **même finalité déclarée** (recommandation personnalisée) et sont collectées séparément de l'inscription, sans jamais être requises pour créer un compte ou utiliser l'application.

### Mesures de sécurité

- **Authentification requise** : seuls les utilisateurs connectés peuvent définir/modifier ces données (endpoints `PATCH /api/v1/auth/me/preferences`, `POST/DELETE /api/v1/favoris/{id}`, `PUT /api/v1/historique/{id}`, `PUT /api/v1/kdramas/{id}/interet`).
- **Row Level Security** : chaque utilisateur ne voit et ne gère que ses propres préférences, favoris et retours d'intérêt (politiques RLS dédiées, voir `preferences_favoris_schema.sql`).
- **Minimisation** : validation applicative des limites (3 genres, 5 acteurs) pour éviter une collecte disproportionnée par rapport à la finalité (art. 5.1.c).
- **Suppression en cascade** : toutes ces données sont supprimées avec le compte (droit à l'effacement, cf. `delete_me`) et incluses dans l'export de portabilité (`GET /api/v1/auth/me/export`).

### Destinataires

| Destinataire | Accès | Finalité |
|---|---|---|
| Utilisateur lui-même | Lecture/écriture de ses propres préférences, favoris et retours d'intérêt | Personnalisation de son expérience |
| Système de recommandation (étape 3) | Lecture | Entraînement et inférence du modèle de recommandation (signal explicite et implicite) |
| Administrateurs | Aucun accès direct aux préférences individuelles (hors export RGPD à la demande de l'utilisateur) | — |

### Durée de conservation

| Donnée | Durée de conservation | Justification |
|---|---|---|
| Genres/acteurs favoris, préférence de fin heureuse | Durée de vie du compte | Nécessaire tant que le compte est actif pour la personnalisation |
| Favoris | Durée de vie du compte | Nécessaire pour la fonctionnalité |
| Retours d'intérêt ("want to watch" / "not interested") | Durée de vie du compte | Signal d'entraînement du modèle de recommandation |
| Toutes les données ci-dessus | Supprimées à l'effacement du compte ou après 2 ans d'inactivité (aligné sur l'historique de visionnage) | Minimisation (art. 5.1.c) |

### Droits des personnes concernées

- **Droit d'accès / rectification** : `GET`/`PATCH /api/v1/auth/me/preferences`, gérable directement depuis la page de profil.
- **Droit à l'effacement** (art. 17) : `DELETE /api/v1/auth/me` supprime favoris, retours d'intérêt et préférences en plus de l'historique de visionnage.
- **Droit à la portabilité** (art. 20) : `GET /api/v1/auth/me/export` inclut désormais ces données.

---

## Traitement n°4 — Journalisation des accès (traçabilité)

### Description

Ce traitement enregistre les accès aux données personnelles des utilisateurs (consultation, modification, suppression) à des fins de traçabilité et d'audit, conformément à l'article 30 du RGPD.

### Données traitées

| Catégorie de données | Données spécifiques | Source | Base légale |
|---|---|---|---|
| Traçabilité | Type d'accès (lecture, écriture, suppression), table ciblée, enregistrement concerné | Système automatique | Intérêt légitime (art. 6.1.f) |
| Technique | Adresse IP, User-Agent | Système automatique | Intérêt légitime (art. 6.1.f) |
| Métadonnées | Date et heure de l'accès | Système automatique | Intérêt légitime (art. 6.1.f) |

### Mesures de sécurité

- **Table dédiée** : `journal_acces` avec index sur la date et le type d'accès.
- **Accès restreint** : seuls les administrateurs et le DPO peuvent consulter le journal.
- **Intégrité** : le journal n'est pas modifiable (INSERT uniquement, pas d'UPDATE/DELETE).

### Destinataires

| Destinataire | Accès | Finalité |
|---|---|---|
| DPO | Lecture | Audit et conformité RGPD |
| Administrateurs | Lecture | Investigation en cas d'incident |

### Durée de conservation

| Donnée | Durée de conservation | Justification |
|---|---|---|
| Journal des accès | 1 an | Traçabilité et audit (recommandation CNIL) |

---

## Traitement n°5 — Collecte de données publiques (K-Dramas, acteurs)

### Description

Ce traitement concerne la collecte de données publiques sur les K-Dramas et les acteurs depuis des sources externes (API TMDB, fichier CSV, scraping MyDramaList). Ces données ne sont pas des données personnelles au sens du RGPD.

### Données traitées

| Catégorie de données | Données spécifiques | Source |
|---|---|---|
| Contenu culturel | Titres, synopsis, dates de diffusion, genres, réseaux | TMDB API, CSV, MyDramaList |
| Informations publiques | Noms d'acteurs, biographies, dates de naissance | TMDB API |

### Note RGPD

Les données collectées sur les K-Dramas et les acteurs sont des données publiques (informations culturelles diffusées publiquement). Elles ne constituent pas des données personnelles au sens du RGPD dans le cadre de ce projet, car :

- Les acteurs sont des personnalités publiques et les informations collectées relèvent du domaine public.
- Les fiches de K-Dramas sont des données culturelles librement accessibles.

Cependant, les mesures suivantes sont appliquées par précaution :

- **Respect des conditions d'utilisation** des sources (TMDB API, MyDramaList).
- **Rate limiting** pour ne pas surcharger les serveurs des sources.
- **Pas de collecte de données personnelles d'utilisateurs** des plateformes sources.

---

## Synthèse des mesures de sécurité techniques

| Mesure | Implémentation | Référence RGPD |
|---|---|---|
| Hachage des emails | SHA-256 via pgcrypto | Art. 32 (sécurité) |
| Hachage des mots de passe | bcrypt via passlib | Art. 32 (sécurité) |
| Chiffrement des tokens | JWT signé (HS256) | Art. 32 (sécurité) |
| Row Level Security | Politiques PostgreSQL RLS | Art. 32 (contrôle d'accès) |
| Journalisation des accès | Table `journal_acces` | Art. 30 (traçabilité) |
| Droit à l'effacement | Fonction `anonymiser_utilisateur()` | Art. 17 |
| Droit à la portabilité | Fonction `exporter_donnees_utilisateur()` | Art. 20 |
| Purge des comptes inactifs | Fonction `purger_comptes_inactifs()` | Art. 5.1.e (conservation) |
| Consentement traçé | Colonnes `consentement_*` et `date_consentement` | Art. 7 |
| Minimisation des données | Pseudonyme au lieu du nom réel | Art. 5.1.c |
| Anonymisation | Vue `v_utilisateurs_anonymises` | Art. 25 (privacy by design) |

---

## Procédure en cas de violation de données

En cas de violation de données personnelles (data breach), la procédure suivante est appliquée :

1. **Détection** : identification de la violation (alerte système, signalement utilisateur).
2. **Confinement** : isolation des systèmes concernés et blocage des accès compromis.
3. **Évaluation** : analyse de la portée de la violation (données concernées, nombre de personnes).
4. **Notification** : notification à la CNIL dans les 72 heures (art. 33).
5. **Information des personnes** : notification aux personnes concernées (art. 34).
6. **Documentation** : enregistrement de la violation dans le journal des accès.
7. **Correctifs** : mise en œuvre des mesures correctives et préventives.

---

*Document généré dans le cadre du projet RNCP — Étape 1 : Collecte et préparation des données.*
