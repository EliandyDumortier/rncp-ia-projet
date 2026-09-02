-- ===========================================================================
-- genre_preferences_by_name_schema.sql — Correction : préférences de genres
-- stockées par NOM plutôt que par clé étrangère vers kdrama.genres.
--
-- Contexte : la table de référence kdrama.genres est alimentée par un seed
-- en français (« Comédie », « Drame », « Fantastique »…, voir la section 14
-- de database_schema.sql), alors que la donnée réelle collectée vit dans la
-- colonne kdramas.genres et utilise les libellés TMDB en anglais
-- (« Action & Adventure », « Sci-Fi & Fantasy », « War & Politics »…).
-- Les deux vocabulaires ne se recoupent que par coïncidence (« Action »,
-- « Crime »).
--
-- Conséquence : la liste proposée à l'utilisateur (GET /api/v1/kdramas/genres,
-- dérivée du catalogue, également utilisée par le filtre de la page Search)
-- ne pouvait jamais être validée contre kdrama.genres, et
-- PATCH /api/v1/auth/me/preferences échouait systématiquement en 400
-- « One or more selected genres do not exist ».
--
-- Ce script applique aux genres exactement le correctif déjà appliqué aux
-- acteurs (actor_preferences_by_name_schema.sql) : le nom sélectionné est
-- stocké directement, dans le même vocabulaire que le catalogue, donc
-- directement exploitable par le moteur de recommandation (étape 3), qui
-- compare aux genres de kdramas.genres.
--
-- Cette migration est sûre à exécuter : la table utilisateur_genres_preferes
-- ne contient aucune ligne au moment de son écriture (vérifié en base) —
-- l'enregistrement des genres favoris n'ayant jamais pu aboutir. Le backfill
-- ci-dessous est néanmoins conservé par précaution.
--
-- Auteur : Équipe Data
-- Projet : Système de recommandation de K-Dramas par IA
-- Étape : 1 — Collecte et préparation des données (correctif)
-- ===========================================================================

SET search_path TO kdrama, public;

ALTER TABLE kdrama.utilisateur_genres_preferes
    ADD COLUMN IF NOT EXISTS genre_nom VARCHAR(100);

-- Backfill défensif : si des lignes existaient malgré tout, on récupère le
-- libellé depuis la table de référence avant de supprimer la clé étrangère.
UPDATE kdrama.utilisateur_genres_preferes ugp
SET genre_nom = g.nom
FROM kdrama.genres g
WHERE ugp.genre_nom IS NULL
  AND ugp.genre_id = g.id;

DELETE FROM kdrama.utilisateur_genres_preferes WHERE genre_nom IS NULL;

ALTER TABLE kdrama.utilisateur_genres_preferes
    DROP CONSTRAINT IF EXISTS utilisateur_genres_preferes_pkey;

ALTER TABLE kdrama.utilisateur_genres_preferes
    DROP CONSTRAINT IF EXISTS utilisateur_genres_preferes_genre_id_fkey;

ALTER TABLE kdrama.utilisateur_genres_preferes
    DROP COLUMN IF EXISTS genre_id;

ALTER TABLE kdrama.utilisateur_genres_preferes
    ALTER COLUMN genre_nom SET NOT NULL;

ALTER TABLE kdrama.utilisateur_genres_preferes
    ADD PRIMARY KEY (utilisateur_id, genre_nom);

COMMENT ON TABLE kdrama.utilisateur_genres_preferes IS
    'Genres favoris optionnels d''un utilisateur (maximum 3, appliqué côté API), stockés par nom (voir GET /api/v1/kdramas/genres, dérivé de kdramas.genres). Utilisé pour la personnalisation des recommandations.';

COMMENT ON COLUMN kdrama.utilisateur_genres_preferes.genre_nom IS
    'Nom du genre favori, dans le vocabulaire du catalogue (colonne kdramas.genres). Pas de FK vers kdrama.genres, dont le seed en français ne correspond pas aux libellés TMDB réellement collectés.';


-- ---------------------------------------------------------------------------
-- Mise à jour de la fonction d'export RGPD (portabilité) : genres_preferes
-- se lit désormais directement depuis genre_nom, sans jointure — comme
-- acteurs_preferes depuis acteur_nom.
-- ---------------------------------------------------------------------------

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
            SELECT COALESCE(json_agg(ugp.genre_nom ORDER BY ugp.genre_nom), '[]'::json)
            FROM kdrama.utilisateur_genres_preferes ugp
            WHERE ugp.utilisateur_id = p_utilisateur_id
        ),
        'acteurs_preferes', (
            SELECT COALESCE(json_agg(uap.acteur_nom ORDER BY uap.acteur_nom), '[]'::json)
            FROM kdrama.utilisateur_acteurs_preferes uap
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
-- Fin du script — genre_preferences_by_name_schema.sql
-- ===========================================================================
