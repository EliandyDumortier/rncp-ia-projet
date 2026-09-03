-- ===========================================================================
-- actor_preferences_by_name_schema.sql — Correction : préférences d'acteurs
-- stockées par NOM plutôt que par clé étrangère vers kdrama.acteurs.
--
-- Contexte : la table kdrama.acteurs n'est pas peuplée par le pipeline de
-- collecte actuel (voir data_collector.py / data_aggregator.py). La donnée
-- réelle des acteurs d'un drama vit uniquement dans la colonne JSON
-- kdramas.acteurs — exactement comme les genres vivent dans kdramas.genres
-- (voir l'endpoint GET /api/v1/kdramas/genres, déjà en place).
--
-- kdrama.utilisateur_acteurs_preferes référençait donc une table vide,
-- rendant l'autocomplétion et l'enregistrement des acteurs favoris
-- impossibles. Ce script corrige la table (créée initialement dans
-- preferences_favoris_schema.sql) pour stocker le nom de l'acteur
-- directement, dérivé de la même source que l'endpoint
-- GET /api/v1/kdramas/actors (nouveau, miroir de kdramas/genres).
--
-- Cette migration est sûre à exécuter : la table utilisateur_acteurs_preferes
-- ne contient encore aucune ligne en production au moment de son écriture.
--
-- Auteur : Équipe Data
-- Projet : Système de recommandation de K-Dramas par IA
-- Étape : 1 — Collecte et préparation des données (correctif)
-- ===========================================================================

SET search_path TO kdrama, public;

ALTER TABLE kdrama.utilisateur_acteurs_preferes
    DROP CONSTRAINT IF EXISTS utilisateur_acteurs_preferes_pkey;

ALTER TABLE kdrama.utilisateur_acteurs_preferes
    DROP CONSTRAINT IF EXISTS utilisateur_acteurs_preferes_acteur_id_fkey;

ALTER TABLE kdrama.utilisateur_acteurs_preferes
    DROP COLUMN IF EXISTS acteur_id;

ALTER TABLE kdrama.utilisateur_acteurs_preferes
    ADD COLUMN IF NOT EXISTS acteur_nom VARCHAR(200);

-- La table est vide à ce stade (aucune préférence enregistrée avant ce
-- correctif), donc NOT NULL + PRIMARY KEY peuvent être appliqués sans
-- backfill.
ALTER TABLE kdrama.utilisateur_acteurs_preferes
    ALTER COLUMN acteur_nom SET NOT NULL;

ALTER TABLE kdrama.utilisateur_acteurs_preferes
    ADD PRIMARY KEY (utilisateur_id, acteur_nom);

COMMENT ON TABLE kdrama.utilisateur_acteurs_preferes IS
    'Acteurs/actrices favoris optionnels d''un utilisateur (maximum 5, appliqué côté API), stockés par nom (voir GET /api/v1/kdramas/actors, dérivé de kdramas.acteurs comme les genres le sont de kdramas.genres). Utilisé pour la personnalisation des recommandations.';

COMMENT ON COLUMN kdrama.utilisateur_acteurs_preferes.acteur_nom IS
    'Nom de l''acteur/actrice favori (texte libre, dérivé du catalogue kdramas.acteurs). Pas de FK vers kdrama.acteurs, cette table n''étant pas peuplée par le pipeline de collecte.';


-- ---------------------------------------------------------------------------
-- Mise à jour de la fonction d'export RGPD (portabilité) : acteurs_preferes
-- se lit désormais directement depuis acteur_nom, sans jointure.
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
            SELECT COALESCE(json_agg(g.nom), '[]'::json)
            FROM kdrama.utilisateur_genres_preferes ugp
            JOIN kdrama.genres g ON ugp.genre_id = g.id
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
-- Fin du script — actor_preferences_by_name_schema.sql
-- ===========================================================================
