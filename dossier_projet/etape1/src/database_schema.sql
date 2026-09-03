-- ===========================================================================
-- database_schema.sql — Schéma DDL PostgreSQL pour la base K-Drama
--
-- Ce script crée l'ensemble du schéma de la base de données K-Drama avec
-- une conformité RGPD (hachage des emails et mots de passe, suivi du
-- consentement, durées de conservation, journalisation des accès,
-- anonymisation, droit à l'effacement).
--
-- Compétence RNCP C4 : Création d'une base de données conforme RGPD
-- (Merise MCD/MLD/MPD).
--
-- Auteur : Équipe Data
-- Projet : Système de recommandation de K-Dramas par IA
-- Étape : 1 — Collecte et préparation des données
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 0. Extensions et configuration
-- ---------------------------------------------------------------------------

-- Extension pgcrypto pour le hachage (SHA-256 des emails)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Extension pg_trgm pour la recherche floue (similarité de texte)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Schéma dédié au projet
CREATE SCHEMA IF NOT EXISTS kdrama;

-- Placer le schéma kdrama en tête du search_path pour que les scripts
-- (sql_queries.py, data_aggregator.py, api_server.py) puissent référencer
-- les tables sans préfixe de schéma.
SET search_path TO kdrama, public;

-- Commentaire de documentation sur le schéma
COMMENT ON SCHEMA kdrama IS 'Schéma de la base de données du système de recommandation de K-Dramas. Conforme au RGPD (règlement UE 2016/679).';


-- ---------------------------------------------------------------------------
-- 1. Table : kdramas (K-Dramas / séries sud-coréennes)
-- ---------------------------------------------------------------------------

CREATE TABLE kdrama.kdramas (
    id                          SERIAL PRIMARY KEY,
    tmdb_id                     INTEGER UNIQUE,
    titre                       VARCHAR(300) NOT NULL,
    titre_original              VARCHAR(300),
    english_name                VARCHAR(300),
    date_diffusion              DATE,
    annee_diffusion             INTEGER,
    -- Colonnes de métadonnées issues de l'agrégation (stockées au format JSON)
    genres                      TEXT,
    acteurs                     TEXT,
    tags                        TEXT,
    reseaux_diffusion           TEXT,
    nb_episodes                 INTEGER CHECK (nb_episodes IS NULL OR nb_episodes > 0),
    nb_saisons                  INTEGER CHECK (nb_saisons IS NULL OR nb_saisons > 0),
    duree_episode_minutes       INTEGER CHECK (duree_episode_minutes IS NULL OR duree_episode_minutes > 0),
    duree_episode               INTEGER CHECK (duree_episode IS NULL OR duree_episode > 0),
    synopsis                    TEXT,
    note_moyenne                NUMERIC(4, 2) CHECK (note_moyenne IS NULL OR (note_moyenne >= 0 AND note_moyenne <= 10)),
    nb_votes                    INTEGER CHECK (nb_votes IS NULL OR nb_votes >= 0),
    langue_originale            VARCHAR(10),
    pays_origine                VARCHAR(10) DEFAULT 'KR',
    source                      VARCHAR(50) NOT NULL DEFAULT 'tmdb',
    url_source                  VARCHAR(500),
    poster                      VARCHAR(500),
    rang                        INTEGER,
    popularite                  DOUBLE PRECISION,
    nb_watchers                 INTEGER,
    realisateur                 VARCHAR(300),
    scenariste                  VARCHAR(300),
    date_creation               TIMESTAMP NOT NULL DEFAULT NOW(),
    date_modification           TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Index pour les recherches fréquentes
CREATE INDEX idx_kdramas_titre ON kdrama.kdramas USING GIN (titre gin_trgm_ops);
CREATE INDEX idx_kdramas_titre_original ON kdrama.kdramas USING GIN (titre_original gin_trgm_ops);
CREATE INDEX idx_kdramas_date_diffusion ON kdrama.kdramas (date_diffusion DESC);
CREATE INDEX idx_kdramas_note_moyenne ON kdrama.kdramas (note_moyenne DESC NULLS LAST);
-- idx_kdramas_annee_diffusion retiré : annee_diffusion est une colonne générée,
-- l'index serait créé automatiquement par PostgreSQL si nécessaire.
CREATE INDEX idx_kdramas_tmdb_id ON kdrama.kdramas (tmdb_id);

COMMENT ON TABLE kdrama.kdramas IS 'Table principale des K-Dramas (séries sud-coréennes).';
COMMENT ON COLUMN kdrama.kdramas.note_moyenne IS 'Note moyenne sur 10 (échelle 0.00 à 10.00).';
COMMENT ON COLUMN kdrama.kdramas.source IS 'Source de la donnée : tmdb, csv, mydramalist.';


-- ---------------------------------------------------------------------------
-- 2. Table : acteurs
-- ---------------------------------------------------------------------------

CREATE TABLE kdrama.acteurs (
    id                          SERIAL PRIMARY KEY,
    tmdb_id                     INTEGER UNIQUE,
    nom                         VARCHAR(200) NOT NULL,
    nom_original                VARCHAR(200),
    date_naissance              DATE,
    sexe                        VARCHAR(1) CHECK (sexe IN ('M', 'F', 'X')),
    biographie                  TEXT,
    photo_url                   VARCHAR(500),
    date_creation               TIMESTAMP NOT NULL DEFAULT NOW(),
    date_modification           TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_acteurs_nom ON kdrama.acteurs USING GIN (nom gin_trgm_ops);
CREATE INDEX idx_acteurs_tmdb_id ON kdrama.acteurs (tmdb_id);

COMMENT ON TABLE kdrama.acteurs IS 'Table des acteurs (comédiens) ayant joué dans des K-Dramas.';


-- ---------------------------------------------------------------------------
-- 3. Table : genres
-- ---------------------------------------------------------------------------

CREATE TABLE kdrama.genres (
    id                          SERIAL PRIMARY KEY,
    nom                         VARCHAR(100) NOT NULL UNIQUE,
    description                 TEXT
);

COMMENT ON TABLE kdrama.genres IS 'Table des genres de K-Dramas (Romance, Comédie, Thriller, etc.).';


-- ---------------------------------------------------------------------------
-- 4. Table : reseaux (réseaux de diffusion)
-- ---------------------------------------------------------------------------

CREATE TABLE kdrama.reseaux (
    id                          SERIAL PRIMARY KEY,
    nom                         VARCHAR(100) NOT NULL,
    pays                        VARCHAR(10) DEFAULT 'KR',
    UNIQUE (nom, pays)
);

COMMENT ON TABLE kdrama.reseaux IS 'Table des réseaux de diffusion (tvN, KBS2, SBS, Netflix, etc.).';


-- ---------------------------------------------------------------------------
-- 5. Tables de liaison (associations plusieurs-à-plusieurs)
-- ---------------------------------------------------------------------------

-- 5a. kdrama_genres : K-Drama <-> Genre
CREATE TABLE kdrama.kdrama_genres (
    kdrama_id                   INTEGER NOT NULL REFERENCES kdrama.kdramas(id) ON DELETE CASCADE,
    genre_id                    INTEGER NOT NULL REFERENCES kdrama.genres(id) ON DELETE CASCADE,
    PRIMARY KEY (kdrama_id, genre_id)
);

CREATE INDEX idx_kdrama_genres_genre ON kdrama.kdrama_genres (genre_id);

COMMENT ON TABLE kdrama.kdrama_genres IS 'Association plusieurs-à-plusieurs entre K-Dramas et genres.';

-- 5b. kdrama_acteurs : K-Drama <-> Acteur
CREATE TABLE kdrama.kdrama_acteurs (
    kdrama_id                   INTEGER NOT NULL REFERENCES kdrama.kdramas(id) ON DELETE CASCADE,
    acteur_id                   INTEGER NOT NULL REFERENCES kdrama.acteurs(id) ON DELETE CASCADE,
    role                        VARCHAR(200),
    role_principal              BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (kdrama_id, acteur_id)
);

CREATE INDEX idx_kdrama_acteurs_acteur ON kdrama.kdrama_acteurs (acteur_id);
CREATE INDEX idx_kdrama_acteurs_principal ON kdrama.kdrama_acteurs (role_principal) WHERE role_principal = TRUE;

COMMENT ON TABLE kdrama.kdrama_acteurs IS 'Association plusieurs-à-plusieurs entre K-Dramas et acteurs, avec rôle et indicateur de rôle principal.';

-- 5c. kdrama_reseaux : K-Drama <-> Réseau
CREATE TABLE kdrama.kdrama_reseaux (
    kdrama_id                   INTEGER NOT NULL REFERENCES kdrama.kdramas(id) ON DELETE CASCADE,
    reseau_id                   INTEGER NOT NULL REFERENCES kdrama.reseaux(id) ON DELETE CASCADE,
    PRIMARY KEY (kdrama_id, reseau_id)
);

COMMENT ON TABLE kdrama.kdrama_reseaux IS 'Association plusieurs-à-plusieurs entre K-Dramas et réseaux de diffusion.';


-- ---------------------------------------------------------------------------
-- 6. Table : utilisateurs (conforme RGPD)
-- ---------------------------------------------------------------------------
-- Mesures RGPD intégrées :
--   - Email haché (SHA-256 via pgcrypto) — pas de stockage en clair.
--   - Mot de passe haché (bcrypt côté application) — pas de stockage en clair.
--   - Suivi du consentement (collecte + marketing) avec date et méthode.
--   - Date de dernière activité pour le calcul de la durée de conservation.
--   - Rôle pour le contrôle d'accès (user / admin).
--   - Pseudonyme pour éviter de stocker le nom réel.
-- ---------------------------------------------------------------------------

CREATE TABLE kdrama.utilisateurs (
    id                          SERIAL PRIMARY KEY,
    pseudonyme                 VARCHAR(100) NOT NULL UNIQUE,
    email_hache                 VARCHAR(64) NOT NULL UNIQUE,
    -- Le mot de passe est haché avec bcrypt côté application (passlib).
    -- La colonne stocke uniquement le hash, jamais le mot de passe en clair.
    mot_de_passe_hache          VARCHAR(255) NOT NULL,
    -- Suivi du consentement RGPD (article 7)
    consentement_collecte       BOOLEAN NOT NULL DEFAULT FALSE,
    consentement_marketing      BOOLEAN NOT NULL DEFAULT FALSE,
    date_consentement           TIMESTAMP,
    methode_consentement        VARCHAR(100),
    -- Rôle pour le contrôle d'accès
    role                        VARCHAR(20) NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    -- Dates pour la gestion de la durée de conservation (RGPD article 5.1.e)
    date_inscription            TIMESTAMP NOT NULL DEFAULT NOW(),
    date_derniere_activite      TIMESTAMP NOT NULL DEFAULT NOW(),
    date_suppression            TIMESTAMP,
    -- Indicateur de compte supprimé/anonymisé (soft delete pour l'intégrité référentielle)
    est_supprime                BOOLEAN NOT NULL DEFAULT FALSE,
    fin_heureuse_uniquement     BOOLEAN NOT NULL DEFAULT FALSE,
    -- Métadonnées
    date_creation               TIMESTAMP NOT NULL DEFAULT NOW(),
    date_modification           TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_utilisateurs_email_hache ON kdrama.utilisateurs (email_hache);
CREATE INDEX idx_utilisateurs_pseudonyme ON kdrama.utilisateurs (pseudonyme);
CREATE INDEX idx_utilisateurs_derniere_activite ON kdrama.utilisateurs (date_derniere_activite);

COMMENT ON TABLE kdrama.utilisateurs IS 'Table des utilisateurs du système de recommandation. Conforme au RGPD : email haché (SHA-256), mot de passe haché (bcrypt), suivi du consentement, durée de conservation via date_derniere_activite.';
COMMENT ON COLUMN kdrama.utilisateurs.email_hache IS 'Hash SHA-256 de l''email. Permet la recherche sans stocker l''email en clair. Calculé via encode(digest(email::bytea, ''sha256''), ''hex'').';
COMMENT ON COLUMN kdrama.utilisateurs.mot_de_passe_hache IS 'Hash bcrypt du mot de passe. Jamais stocké en clair. Hachage effectué côté application avec passlib.';
COMMENT ON COLUMN kdrama.utilisateurs.consentement_collecte IS 'Consentement de l''utilisateur à la collecte de ses données (RGPD art. 6.1.a).';
COMMENT ON COLUMN kdrama.utilisateurs.consentement_marketing IS 'Consentement de l''utilisateur à recevoir des communications marketing (RGPD art. 7).';
COMMENT ON COLUMN kdrama.utilisateurs.date_derniere_activite IS 'Date de dernière activité. Utilisée pour calculer la durée de conservation (comptes inactifs > 3 ans supprimés).';
COMMENT ON COLUMN kdrama.utilisateurs.est_supprime IS 'Indicateur de compte supprimé/anonymisé (soft delete). Le compte est conservé pour l''intégrité référentielle mais anonymisé.';


-- ---------------------------------------------------------------------------
-- 7. Table : notes (notes des utilisateurs sur les K-Dramas)
-- ---------------------------------------------------------------------------

CREATE TABLE kdrama.notes (
    id                          SERIAL PRIMARY KEY,
    utilisateur_id              INTEGER NOT NULL REFERENCES kdrama.utilisateurs(id) ON DELETE CASCADE,
    kdrama_id                   INTEGER NOT NULL REFERENCES kdrama.kdramas(id) ON DELETE CASCADE,
    note                        INTEGER NOT NULL CHECK (note >= 1 AND note <= 10),
    commentaire                 TEXT,
    date_note                   TIMESTAMP NOT NULL DEFAULT NOW(),
    date_modification           TIMESTAMP,
    UNIQUE (utilisateur_id, kdrama_id)
);

CREATE INDEX idx_notes_utilisateur ON kdrama.notes (utilisateur_id);
CREATE INDEX idx_notes_kdrama ON kdrama.notes (kdrama_id);
CREATE INDEX idx_notes_date ON kdrama.notes (date_note DESC);

COMMENT ON TABLE kdrama.notes IS 'Table des notes attribuées par les utilisateurs aux K-Dramas. Une note par utilisateur et par K-Drama (contrainte UNIQUE).';


-- ---------------------------------------------------------------------------
-- 8. Table : avis (critiques textuelles des utilisateurs)
-- ---------------------------------------------------------------------------

CREATE TABLE kdrama.avis (
    id                          SERIAL PRIMARY KEY,
    utilisateur_id              INTEGER NOT NULL REFERENCES kdrama.utilisateurs(id) ON DELETE CASCADE,
    kdrama_id                   INTEGER NOT NULL REFERENCES kdrama.kdramas(id) ON DELETE CASCADE,
    titre                        VARCHAR(200),
    contenu                     TEXT NOT NULL,
    statut                      VARCHAR(20) NOT NULL DEFAULT 'publie' CHECK (statut IN ('brouillon', 'publie', 'masque', 'signale')),
    date_publication            TIMESTAMP NOT NULL DEFAULT NOW(),
    date_modification           TIMESTAMP
);

CREATE INDEX idx_avis_utilisateur ON kdrama.avis (utilisateur_id);
CREATE INDEX idx_avis_kdrama ON kdrama.avis (kdrama_id);
CREATE INDEX idx_avis_statut ON kdrama.avis (statut);

COMMENT ON TABLE kdrama.avis IS 'Table des avis/critiques textuelles des utilisateurs sur les K-Dramas.';


-- ---------------------------------------------------------------------------
-- 9. Table : historique_visionnage (RGPD — données personnelles)
-- ---------------------------------------------------------------------------

CREATE TABLE kdrama.historique_visionnage (
    id                          SERIAL PRIMARY KEY,
    utilisateur_id              INTEGER NOT NULL REFERENCES kdrama.utilisateurs(id) ON DELETE CASCADE,
    kdrama_id                   INTEGER NOT NULL REFERENCES kdrama.kdramas(id) ON DELETE CASCADE,
    episodes_vus                INTEGER DEFAULT 0,
    statut                      VARCHAR(20) DEFAULT 'en_cours' CHECK (statut IN ('a_voir', 'en_cours', 'termine', 'abandonne')),
    date_debut                  TIMESTAMP,
    date_fin                    TIMESTAMP,
    date_creation               TIMESTAMP NOT NULL DEFAULT NOW(),
    date_modification           TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_historique_utilisateur ON kdrama.historique_visionnage (utilisateur_id);
CREATE INDEX idx_historique_kdrama ON kdrama.historique_visionnage (kdrama_id);

COMMENT ON TABLE kdrama.historique_visionnage IS 'Historique de visionnage des utilisateurs. Donnée personnelle soumise au RGPD. Supprimée en cascade avec l''utilisateur (droit à l''effacement).';


-- ---------------------------------------------------------------------------
-- 10. Table : journal_acces (RGPD — traçabilité des accès aux données perso)
-- ---------------------------------------------------------------------------

CREATE TABLE kdrama.journal_acces (
    id                          SERIAL PRIMARY KEY,
    utilisateur_id              INTEGER REFERENCES kdrama.utilisateurs(id) ON DELETE SET NULL,
    type_acces                  VARCHAR(50) NOT NULL,
    table_cible                 VARCHAR(100),
    enregistrement_id           INTEGER,
    date_acces                  TIMESTAMP NOT NULL DEFAULT NOW(),
    adresse_ip                  INET,
    user_agent                  TEXT,
    details                     TEXT
);

CREATE INDEX idx_journal_utilisateur ON kdrama.journal_acces (utilisateur_id);
CREATE INDEX idx_journal_date ON kdrama.journal_acces (date_acces DESC);
CREATE INDEX idx_journal_type ON kdrama.journal_acces (type_acces);

COMMENT ON TABLE kdrama.journal_acces IS 'Journal des accès aux données personnelles (RGPD art. 30, traçabilité). Enregistre chaque consultation, modification ou suppression de données utilisateur.';


-- ---------------------------------------------------------------------------
-- 11. Vues SQL (pour l'extraction et l'anonymisation RGPD)
-- ---------------------------------------------------------------------------

-- Vue 1 : K-Dramas populaires (note >= 7.0 et >= 100 votes)
CREATE OR REPLACE VIEW kdrama.v_kdramas_populaires AS
SELECT
    k.id,
    k.titre,
    k.titre_original,
    k.date_diffusion,
    k.nb_episodes,
    k.note_moyenne,
    k.nb_votes,
    STRING_AGG(g.nom, ', ' ORDER BY g.nom) AS liste_genres
FROM kdrama.kdramas k
LEFT JOIN kdrama.kdrama_genres kg ON k.id = kg.kdrama_id
LEFT JOIN kdrama.genres g ON kg.genre_id = g.id
WHERE k.note_moyenne >= 7.0 AND k.nb_votes >= 100
GROUP BY k.id, k.titre, k.titre_original, k.date_diffusion,
         k.nb_episodes, k.note_moyenne, k.nb_votes
ORDER BY k.note_moyenne DESC;

COMMENT ON VIEW kdrama.v_kdramas_populaires IS 'Vue des K-Dramas populaires (note >= 7.0 et >= 100 votes) avec genres agrégés.';

-- Vue 2 : Statistiques par acteur
CREATE OR REPLACE VIEW kdrama.v_stats_acteurs AS
SELECT
    a.id,
    a.nom,
    a.nom_original,
    COUNT(ka.kdrama_id) AS nombre_kdramas,
    ROUND(AVG(k.note_moyenne), 2) AS note_moyenne_filmo,
    MAX(k.date_diffusion) AS derniere_apparition
FROM kdrama.acteurs a
LEFT JOIN kdrama.kdrama_acteurs ka ON a.id = ka.acteur_id
LEFT JOIN kdrama.kdramas k ON ka.kdrama_id = k.id
GROUP BY a.id, a.nom, a.nom_original;

COMMENT ON VIEW kdrama.v_stats_acteurs IS 'Vue des statistiques par acteur (nombre de K-Dramas, note moyenne de la filmographie).';

-- Vue 3 : Utilisateurs anonymisés (RGPD — pas d'email ni de hash exposés)
CREATE OR REPLACE VIEW kdrama.v_utilisateurs_anonymises AS
SELECT
    id,
    pseudonyme,
    date_inscription,
    consentement_collecte,
    consentement_marketing,
    date_consentement,
    role,
    date_derniere_activite,
    est_supprime
FROM kdrama.utilisateurs
WHERE est_supprime = FALSE;

COMMENT ON VIEW kdrama.v_utilisateurs_anonymises IS 'Vue anonymisée des utilisateurs (RGPD). N''expose pas l''email haché ni le mot de passe. Utilisée pour les statistiques et l''administration.';


-- ---------------------------------------------------------------------------
-- 12. Fonctions SQL (RGPD — conformité et maintenance)
-- ---------------------------------------------------------------------------

-- Fonction 1 : Hachage d'un email (SHA-256) pour insertion sécurisée
CREATE OR REPLACE FUNCTION kdrama.hacher_email(p_email TEXT)
RETURNS VARCHAR(64) AS $$
BEGIN
    -- Normalisation : lowercase + trim avant hachage
    RETURN encode(digest(LOWER(TRIM(p_email))::bytea, 'sha256'), 'hex');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION kdrama.hacher_email(TEXT) IS 'Hache un email avec SHA-256 (pgcrypto). Utilisé pour stocker l''email sans le révéler en clair, tout en permettant la recherche par hash.';

-- Fonction 2 : Mise à jour automatique de date_modification
CREATE OR REPLACE FUNCTION kdrama.update_date_modification()
RETURNS TRIGGER AS $$
BEGIN
    NEW.date_modification = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers de mise à jour automatique de date_modification
CREATE TRIGGER trg_kdramas_modification
    BEFORE UPDATE ON kdrama.kdramas
    FOR EACH ROW EXECUTE FUNCTION kdrama.update_date_modification();

CREATE TRIGGER trg_acteurs_modification
    BEFORE UPDATE ON kdrama.acteurs
    FOR EACH ROW EXECUTE FUNCTION kdrama.update_date_modification();

CREATE TRIGGER trg_utilisateurs_modification
    BEFORE UPDATE ON kdrama.utilisateurs
    FOR EACH ROW EXECUTE FUNCTION kdrama.update_date_modification();

-- Fonction 3 : Purge des comptes inactifs (RGPD art. 5.1.e — limitation de conservation)
-- Supprime les comptes inactifs depuis plus de 3 ans.
CREATE OR REPLACE FUNCTION kdrama.purger_comptes_inactifs(
    p_duree_inactivite_mois INTEGER DEFAULT 36
)
RETURNS INTEGER AS $$
DECLARE
    nb_supprimes INTEGER;
BEGIN
    DELETE FROM kdrama.utilisateurs
    WHERE date_derniere_activite < NOW() - (p_duree_inactivite_mois || ' months')::INTERVAL
      AND est_supprime = FALSE;

    GET DIAGNOSTICS nb_supprimes = ROW_COUNT;

    -- Journalisation de la purge
    INSERT INTO kdrama.journal_acces (type_acces, table_cible, details)
    VALUES ('purge_inactifs', 'utilisateurs',
            'Purge automatique de ' || nb_supprimes || ' comptes inactifs depuis ' || p_duree_inactivite_mois || ' mois');

    RETURN nb_supprimes;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION kdrama.purger_comptes_inactifs(INTEGER) IS 'Purge les comptes inactifs depuis plus de N mois (défaut: 36 mois = 3 ans). Implémente le principe de limitation de conservation du RGPD (art. 5.1.e).';

-- Fonction 4 : Droit à l'effacement (RGPD art. 17)
-- Anonymise un compte utilisateur au lieu de le supprimer physiquement
-- (préservation de l'intégrité référentielle pour les notes et avis existants).
CREATE OR REPLACE FUNCTION kdrama.anonymiser_utilisateur(p_utilisateur_id INTEGER)
RETURNS BOOLEAN AS $$
DECLARE
    success BOOLEAN := FALSE;
BEGIN
    -- Vérification de l'existence du compte
    IF NOT EXISTS (SELECT 1 FROM kdrama.utilisateurs WHERE id = p_utilisateur_id AND est_supprime = FALSE) THEN
        RETURN FALSE;
    END IF;

    -- Anonymisation du compte (pseudonyme remplacé, email et mot de passe effacés)
    UPDATE kdrama.utilisateurs
    SET
        pseudonyme = 'utilisateur_supprime_' || p_utilisateur_id,
        email_hache = 'ANONYMIZED_' || p_utilisateur_id,
        mot_de_passe_hache = 'ANONYMIZED',
        consentement_collecte = FALSE,
        consentement_marketing = FALSE,
        date_consentement = NULL,
        methode_consentement = NULL,
        est_supprime = TRUE,
        date_suppression = NOW(),
        date_derniere_activite = NOW()
    WHERE id = p_utilisateur_id;

    -- Suppression de l'historique de visionnage (donnée personlle sensible)
    DELETE FROM kdrama.historique_visionnage WHERE utilisateur_id = p_utilisateur_id;

    -- Journalisation de l'effacement
    INSERT INTO kdrama.journal_acces (utilisateur_id, type_acces, table_cible, details)
    VALUES (p_utilisateur_id, 'effacement_rgpd', 'utilisateurs',
            'Droit à l''effacement (RGPD art. 17) — compte anonymisé');

    success := TRUE;
    RETURN success;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION kdrama.anonymiser_utilisateur(INTEGER) IS 'Implémente le droit à l''effacement (RGPD art. 17). Anonymise le compte au lieu de le supprimer physiquement pour préserver l''intégrité référentielle des notes et avis.';

-- Fonction 5 : Export des données utilisateur (RGPD art. 20 — portabilité)
CREATE OR REPLACE FUNCTION kdrama.exporter_donnees_utilisateur(p_utilisateur_id INTEGER)
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_build_object(
        'utilisateur', (
            SELECT row_to_json(u) FROM (
                SELECT id, pseudonyme, date_inscription, role, date_derniere_activite
                FROM kdrama.utilisateurs
                WHERE id = p_utilisateur_id AND est_supprime = FALSE
            ) u
        ),
        'notes', (
            SELECT COALESCE(json_agg(row_to_json(n)), '[]'::json) FROM (
                SELECT n.id, k.titre AS kdrama, n.note, n.commentaire, n.date_note
                FROM kdrama.notes n
                JOIN kdrama.kdramas k ON n.kdrama_id = k.id
                WHERE n.utilisateur_id = p_utilisateur_id
                ORDER BY n.date_note DESC
            ) n
        ),
        'avis', (
            SELECT COALESCE(json_agg(row_to_json(a)), '[]'::json) FROM (
                SELECT a.id, k.titre AS kdrama, a.titre, a.contenu, a.date_publication
                FROM kdrama.avis a
                JOIN kdrama.kdramas k ON a.kdrama_id = k.id
                WHERE a.utilisateur_id = p_utilisateur_id
                ORDER BY a.date_publication DESC
            ) a
        ),
        'historique_visionnage', (
            SELECT COALESCE(json_agg(row_to_json(h)), '[]'::json) FROM (
                SELECT h.id, k.titre AS kdrama, h.episodes_vus, h.statut, h.date_debut, h.date_fin
                FROM kdrama.historique_visionnage h
                JOIN kdrama.kdramas k ON h.kdrama_id = k.id
                WHERE h.utilisateur_id = p_utilisateur_id
                ORDER BY h.date_creation DESC
            ) h
        )
    ) INTO result;

    -- Journalisation de l'export
    INSERT INTO kdrama.journal_acces (utilisateur_id, type_acces, table_cible, details)
    VALUES (p_utilisateur_id, 'export_donnees', 'utilisateurs',
            'Portabilité des données (RGPD art. 20)');

    RETURN result;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION kdrama.exporter_donnees_utilisateur(INTEGER) IS 'Exporte toutes les données d''un utilisateur au format JSON (RGPD art. 20 — droit à la portabilité).';


-- ---------------------------------------------------------------------------
-- 13. Politiques de sécurité au niveau des lignes (Row Level Security)
-- ---------------------------------------------------------------------------

-- Activation du RLS sur la table utilisateurs
ALTER TABLE kdrama.utilisateurs ENABLE ROW LEVEL SECURITY;

-- Politique : un utilisateur ne voit que ses propres données
CREATE POLICY politique_utilisateur_self ON kdrama.utilisateurs
    FOR SELECT
    USING (id = current_setting('app.current_user_id', TRUE)::INTEGER
           OR est_supprime = FALSE);

-- Politique : les admins voient et gèrent tous les comptes
CREATE POLICY politique_admin_all ON kdrama.utilisateurs
    FOR ALL
    USING (current_setting('app.current_role', TRUE) = 'admin')
    WITH CHECK (current_setting('app.current_role', TRUE) = 'admin');

-- Activation du RLS sur la table notes
ALTER TABLE kdrama.notes ENABLE ROW LEVEL SECURITY;

-- Politique : un utilisateur ne voit et ne gère que ses propres notes
CREATE POLICY politique_notes_self ON kdrama.notes
    FOR ALL
    USING (utilisateur_id = current_setting('app.current_user_id', TRUE)::INTEGER)
    WITH CHECK (utilisateur_id = current_setting('app.current_user_id', TRUE)::INTEGER);

-- Politique : les notes sont visibles par tous pour les recommandations
-- (mais les commentaires ne sont exposés que via l'API authentifiée)
CREATE POLICY politique_notes_public_read ON kdrama.notes
    FOR SELECT
    USING (TRUE);

-- Activation du RLS sur la table historique_visionnage
ALTER TABLE kdrama.historique_visionnage ENABLE ROW LEVEL SECURITY;

-- Politique : un utilisateur ne voit et ne gère que son propre historique
CREATE POLICY politique_historique_self ON kdrama.historique_visionnage
    FOR ALL
    USING (utilisateur_id = current_setting('app.current_user_id', TRUE)::INTEGER)
    WITH CHECK (utilisateur_id = current_setting('app.current_user_id', TRUE)::INTEGER);


-- ---------------------------------------------------------------------------
-- 14. Données de référence (seed — genres de base)
-- ---------------------------------------------------------------------------

INSERT INTO kdrama.genres (nom, description) VALUES
    ('Romance', 'Histoires d''amour et relations amoureuses'),
    ('Comédie', 'Séries humoristiques et légères'),
    ('Comédie romantique', 'Mélange de romance et de comédie'),
    ('Drame', 'Séries dramatiques avec thèmes profonds'),
    ('Mélodrame', 'Drames émotionnels intenses'),
    ('Thriller', 'Suspense, tension et mystère'),
    ('Mystère', 'Enquêtes et résolution de puzzles'),
    ('Historique', 'Séries se déroulant dans un contexte historique'),
    ('Fantastique', 'Éléments surnaturels et magie'),
    ('Action', 'Scènes d''action et aventures'),
    ('Crime', 'Criminalité, enquêtes policières'),
    ('Politique', 'Intrigues politiques et pouvoir'),
    ('Médical', 'Séries se déroulant dans un milieu médical'),
    ('Juridique', 'Avocats, justice et procès'),
    ('Surnaturel', 'Fantômes, esprits et phénomènes inexpliqués'),
    ('Horreur', 'Séries d''épouvante et d''horreur'),
    ('Science-fiction', 'Futur, technologie et concepts scientifiques'),
    ('Famille', 'Dynamiques familiales et relations'),
    ('Amitié', 'Relations d''amitié et camaraderie'),
    ('Tranche de vie', 'Quotidien et moments de vie'),
    ('Musique', 'Industrie musicale et performances'),
    ('Sport', 'Compétitions sportives et entraînement'),
    ('Business', 'Monde de l''entreprise et du commerce'),
    ('Jeunesse', 'Vie de jeunes adultes et étudiants'),
    ('École', 'Milieu scolaire et universitaire'),
    ('Psychologique', 'Thrillers psychologiques et exploration mentale'),
    ('Militaire', 'Contexte militaire et armée'),
    ('Espionnage', 'Agents secrets et renseignements'),
    ('Zombie', 'Apocalypse zombie et survie'),
    ('Vampire', 'Vampires et mythologie vampirique'),
    ('Voyage dans le temps', 'Voyage temporel et paradoxes')
ON CONFLICT (nom) DO NOTHING;


-- ---------------------------------------------------------------------------
-- 15. Données de référence (seed — réseaux de diffusion)
-- ---------------------------------------------------------------------------

INSERT INTO kdrama.reseaux (nom, pays) VALUES
    ('tvN', 'KR'),
    ('KBS2', 'KR'),
    ('SBS', 'KR'),
    ('MBC', 'KR'),
    ('JTBC', 'KR'),
    ('OCN', 'KR'),
    ('Netflix', 'KR'),
    ('Disney+', 'KR'),
    ('KakaoTV', 'KR'),
    ('Wavve', 'KR'),
    ('Tving', 'KR'),
    ('ENA', 'KR'),
    ('Channel A', 'KR'),
    ('MBN', 'KR')
ON CONFLICT (nom, pays) DO NOTHING;


-- ===========================================================================
-- Fin du script — database_schema.sql
-- ===========================================================================
