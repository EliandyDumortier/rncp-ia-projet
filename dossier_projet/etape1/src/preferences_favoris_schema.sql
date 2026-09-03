-- ===========================================================================
-- preferences_favoris_schema.sql — Préférences de recommandation, favoris
-- et retours utilisateur ("want to watch" / "not interested").
--
-- Ce script étend le schéma de database_schema.sql de façon additive
-- (aucune table existante n'est modifiée en profondeur, uniquement des
-- ajouts de colonnes/tables). Il est conforme au RGPD au même titre que le
-- reste du schéma : toutes les nouvelles données sont optionnelles,
-- collectées dans le seul but d'améliorer les recommandations, et
-- supprimées avec le compte utilisateur (ON DELETE CASCADE) ou lors de
-- l'anonymisation (cf. fonction kdrama.anonymiser_utilisateur ci-dessous).
--
-- Compétence RNCP C4 (suite) : évolution du schéma RGPD pour l'étape 3
-- (modèle de recommandation) et l'étape 4 (page recommandations/profil).
--
-- Auteur : Équipe Data
-- Projet : Système de recommandation de K-Dramas par IA
-- Étape : 1 — Collecte et préparation des données (évolution)
-- ===========================================================================

SET search_path TO kdrama, public;

-- ---------------------------------------------------------------------------
-- 1. Préférence "fin heureuse uniquement" sur le compte utilisateur
-- ---------------------------------------------------------------------------

ALTER TABLE kdrama.utilisateurs
    ADD COLUMN IF NOT EXISTS fin_heureuse_uniquement BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN kdrama.utilisateurs.fin_heureuse_uniquement IS
    'Préférence optionnelle de recommandation : si TRUE, ne recommander que des dramas à fin heureuse (voir kdrama.drama_sentiments.ending_type). Modifiable par l''utilisateur depuis son profil.';


-- ---------------------------------------------------------------------------
-- 2. Table : utilisateur_genres_preferes (genres favoris, max 3 côté API)
-- ---------------------------------------------------------------------------
-- Mirroir de kdrama_genres, mais côté préférences utilisateur plutôt que
-- métadonnées de drama. La limite de 3 genres est appliquée dans l'API
-- (api_server.py), pas en contrainte SQL, pour rester simple à faire évoluer.

CREATE TABLE IF NOT EXISTS kdrama.utilisateur_genres_preferes (
    utilisateur_id              INTEGER NOT NULL REFERENCES kdrama.utilisateurs(id) ON DELETE CASCADE,
    genre_id                    INTEGER NOT NULL REFERENCES kdrama.genres(id) ON DELETE CASCADE,
    date_ajout                  TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (utilisateur_id, genre_id)
);

CREATE INDEX IF NOT EXISTS idx_utilisateur_genres_preferes_utilisateur
    ON kdrama.utilisateur_genres_preferes (utilisateur_id);

COMMENT ON TABLE kdrama.utilisateur_genres_preferes IS
    'Genres favoris optionnels d''un utilisateur (maximum 3, appliqué côté API). Utilisé pour la personnalisation des recommandations.';


-- ---------------------------------------------------------------------------
-- 3. Table : utilisateur_acteurs_preferes (acteurs favoris, max 5 côté API)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS kdrama.utilisateur_acteurs_preferes (
    utilisateur_id              INTEGER NOT NULL REFERENCES kdrama.utilisateurs(id) ON DELETE CASCADE,
    acteur_id                   INTEGER NOT NULL REFERENCES kdrama.acteurs(id) ON DELETE CASCADE,
    date_ajout                  TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (utilisateur_id, acteur_id)
);

CREATE INDEX IF NOT EXISTS idx_utilisateur_acteurs_preferes_utilisateur
    ON kdrama.utilisateur_acteurs_preferes (utilisateur_id);

COMMENT ON TABLE kdrama.utilisateur_acteurs_preferes IS
    'Acteurs/actrices favoris optionnels d''un utilisateur (maximum 5, appliqué côté API). Utilisé pour la personnalisation des recommandations.';


-- ---------------------------------------------------------------------------
-- 4. Table : favoris (liste de favoris K-Drama, distincte des notes)
-- ---------------------------------------------------------------------------
-- Aucune table existante ne modélisait déjà ce "bookmark" simple
-- (kdrama.notes sert à la notation 1-10, pas à une liste de favoris).

CREATE TABLE IF NOT EXISTS kdrama.favoris (
    id                          SERIAL PRIMARY KEY,
    utilisateur_id              INTEGER NOT NULL REFERENCES kdrama.utilisateurs(id) ON DELETE CASCADE,
    kdrama_id                   INTEGER NOT NULL REFERENCES kdrama.kdramas(id) ON DELETE CASCADE,
    date_ajout                  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (utilisateur_id, kdrama_id)
);

CREATE INDEX IF NOT EXISTS idx_favoris_utilisateur ON kdrama.favoris (utilisateur_id);
CREATE INDEX IF NOT EXISTS idx_favoris_kdrama ON kdrama.favoris (kdrama_id);

COMMENT ON TABLE kdrama.favoris IS
    'Liste de favoris (bookmarks) d''un utilisateur. Donnée personnelle RGPD, supprimée en cascade avec le compte.';


-- ---------------------------------------------------------------------------
-- 5. Table : interet_utilisateur (retour "want to watch" / "not interested")
-- ---------------------------------------------------------------------------
-- Distincte de historique_visionnage (qui suit le visionnage réel :
-- a_voir/en_cours/termine/abandonne). Ici il s'agit d'un signal explicite
-- donné depuis la fiche drama, avant tout visionnage, qui sert à la fois
-- l'expérience utilisateur et l'entraînement du modèle de recommandation.

CREATE TABLE IF NOT EXISTS kdrama.interet_utilisateur (
    id                          SERIAL PRIMARY KEY,
    utilisateur_id              INTEGER NOT NULL REFERENCES kdrama.utilisateurs(id) ON DELETE CASCADE,
    kdrama_id                   INTEGER NOT NULL REFERENCES kdrama.kdramas(id) ON DELETE CASCADE,
    interesse                   BOOLEAN NOT NULL,
    date_creation               TIMESTAMP NOT NULL DEFAULT NOW(),
    date_modification           TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (utilisateur_id, kdrama_id)
);

CREATE INDEX IF NOT EXISTS idx_interet_utilisateur_utilisateur
    ON kdrama.interet_utilisateur (utilisateur_id);
CREATE INDEX IF NOT EXISTS idx_interet_utilisateur_kdrama
    ON kdrama.interet_utilisateur (kdrama_id);

COMMENT ON TABLE kdrama.interet_utilisateur IS
    'Retour explicite "je veux regarder" (interesse=TRUE) / "pas interesse" (interesse=FALSE) donné depuis la fiche drama. Alimente l''expérience utilisateur et le modèle de recommandation (étape 3). Donnée personnelle RGPD, supprimée en cascade avec le compte.';

CREATE TRIGGER trg_interet_utilisateur_modification
    BEFORE UPDATE ON kdrama.interet_utilisateur
    FOR EACH ROW EXECUTE FUNCTION kdrama.update_date_modification();


-- ---------------------------------------------------------------------------
-- 6. Row Level Security sur les nouvelles tables personnelles
-- ---------------------------------------------------------------------------

ALTER TABLE kdrama.utilisateur_genres_preferes ENABLE ROW LEVEL SECURITY;
CREATE POLICY politique_genres_preferes_self ON kdrama.utilisateur_genres_preferes
    FOR ALL
    USING (utilisateur_id = current_setting('app.current_user_id', TRUE)::INTEGER)
    WITH CHECK (utilisateur_id = current_setting('app.current_user_id', TRUE)::INTEGER);

ALTER TABLE kdrama.utilisateur_acteurs_preferes ENABLE ROW LEVEL SECURITY;
CREATE POLICY politique_acteurs_preferes_self ON kdrama.utilisateur_acteurs_preferes
    FOR ALL
    USING (utilisateur_id = current_setting('app.current_user_id', TRUE)::INTEGER)
    WITH CHECK (utilisateur_id = current_setting('app.current_user_id', TRUE)::INTEGER);

ALTER TABLE kdrama.favoris ENABLE ROW LEVEL SECURITY;
CREATE POLICY politique_favoris_self ON kdrama.favoris
    FOR ALL
    USING (utilisateur_id = current_setting('app.current_user_id', TRUE)::INTEGER)
    WITH CHECK (utilisateur_id = current_setting('app.current_user_id', TRUE)::INTEGER);

ALTER TABLE kdrama.interet_utilisateur ENABLE ROW LEVEL SECURITY;
CREATE POLICY politique_interet_utilisateur_self ON kdrama.interet_utilisateur
    FOR ALL
    USING (utilisateur_id = current_setting('app.current_user_id', TRUE)::INTEGER)
    WITH CHECK (utilisateur_id = current_setting('app.current_user_id', TRUE)::INTEGER);


-- ---------------------------------------------------------------------------
-- 7. Mise à jour des fonctions RGPD existantes (droit à l'effacement /
--    portabilité) pour couvrir les nouvelles tables.
-- ---------------------------------------------------------------------------
-- Remplace kdrama.anonymiser_utilisateur pour supprimer aussi les nouvelles
-- données personnelles (favoris, intérêts, préférences) au même titre que
-- l'historique de visionnage.

CREATE OR REPLACE FUNCTION kdrama.anonymiser_utilisateur(p_utilisateur_id INTEGER)
RETURNS BOOLEAN AS $$
DECLARE
    success BOOLEAN := FALSE;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM kdrama.utilisateurs WHERE id = p_utilisateur_id AND est_supprime = FALSE) THEN
        RETURN FALSE;
    END IF;

    UPDATE kdrama.utilisateurs
    SET
        pseudonyme = 'utilisateur_supprime_' || p_utilisateur_id,
        email_hache = 'ANONYMIZED_' || p_utilisateur_id,
        mot_de_passe_hache = 'ANONYMIZED',
        consentement_collecte = FALSE,
        consentement_marketing = FALSE,
        date_consentement = NULL,
        methode_consentement = NULL,
        fin_heureuse_uniquement = FALSE,
        est_supprime = TRUE,
        date_suppression = NOW(),
        date_derniere_activite = NOW()
    WHERE id = p_utilisateur_id;

    -- Suppression de toutes les données personnelles liées aux préférences
    -- de recommandation (RGPD art. 17 — droit à l'effacement).
    DELETE FROM kdrama.historique_visionnage WHERE utilisateur_id = p_utilisateur_id;
    DELETE FROM kdrama.favoris WHERE utilisateur_id = p_utilisateur_id;
    DELETE FROM kdrama.interet_utilisateur WHERE utilisateur_id = p_utilisateur_id;
    DELETE FROM kdrama.utilisateur_genres_preferes WHERE utilisateur_id = p_utilisateur_id;
    DELETE FROM kdrama.utilisateur_acteurs_preferes WHERE utilisateur_id = p_utilisateur_id;

    INSERT INTO kdrama.journal_acces (utilisateur_id, type_acces, table_cible, details)
    VALUES (p_utilisateur_id, 'effacement_rgpd', 'utilisateurs',
            'Droit à l''effacement (RGPD art. 17) — compte anonymisé (incl. favoris, intérêts, préférences)');

    success := TRUE;
    RETURN success;
END;
$$ LANGUAGE plpgsql;

-- Remplace kdrama.exporter_donnees_utilisateur pour inclure les nouvelles
-- données personnelles dans l'export de portabilité (RGPD art. 20).

CREATE OR REPLACE FUNCTION kdrama.exporter_donnees_utilisateur(p_utilisateur_id INTEGER)
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_build_object(
        'utilisateur', (
            SELECT row_to_json(u) FROM (
                SELECT id, pseudonyme, date_inscription, role, date_derniere_activite,
                       fin_heureuse_uniquement
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
        ),
        'favoris', (
            SELECT COALESCE(json_agg(row_to_json(f)), '[]'::json) FROM (
                SELECT f.id, k.titre AS kdrama, f.date_ajout
                FROM kdrama.favoris f
                JOIN kdrama.kdramas k ON f.kdrama_id = k.id
                WHERE f.utilisateur_id = p_utilisateur_id
                ORDER BY f.date_ajout DESC
            ) f
        ),
        'interets', (
            SELECT COALESCE(json_agg(row_to_json(i)), '[]'::json) FROM (
                SELECT i.id, k.titre AS kdrama, i.interesse, i.date_creation
                FROM kdrama.interet_utilisateur i
                JOIN kdrama.kdramas k ON i.kdrama_id = k.id
                WHERE i.utilisateur_id = p_utilisateur_id
                ORDER BY i.date_creation DESC
            ) i
        ),
        'genres_preferes', (
            SELECT COALESCE(json_agg(g.nom), '[]'::json)
            FROM kdrama.utilisateur_genres_preferes ugp
            JOIN kdrama.genres g ON ugp.genre_id = g.id
            WHERE ugp.utilisateur_id = p_utilisateur_id
        ),
        'acteurs_preferes', (
            SELECT COALESCE(json_agg(a.nom), '[]'::json)
            FROM kdrama.utilisateur_acteurs_preferes uap
            JOIN kdrama.acteurs a ON uap.acteur_id = a.id
            WHERE uap.utilisateur_id = p_utilisateur_id
        )
    ) INTO result;

    INSERT INTO kdrama.journal_acces (utilisateur_id, type_acces, table_cible, details)
    VALUES (p_utilisateur_id, 'export_donnees', 'utilisateurs',
            'Portabilité des données (RGPD art. 20)');

    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- ===========================================================================
-- Fin du script — preferences_favoris_schema.sql
-- ===========================================================================
