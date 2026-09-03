-- Additive compatibility migration for the current FastAPI ORM.
-- Safe to execute repeatedly and on existing Docker volumes.

ALTER TABLE kdrama.kdramas
    ADD COLUMN IF NOT EXISTS english_name VARCHAR(300),
    ADD COLUMN IF NOT EXISTS poster VARCHAR(500),
    ADD COLUMN IF NOT EXISTS duree_episode INTEGER,
    ADD COLUMN IF NOT EXISTS rang INTEGER,
    ADD COLUMN IF NOT EXISTS popularite DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS nb_watchers INTEGER,
    ADD COLUMN IF NOT EXISTS realisateur VARCHAR(300),
    ADD COLUMN IF NOT EXISTS scenariste VARCHAR(300);

ALTER TABLE kdrama.utilisateurs
    ADD COLUMN IF NOT EXISTS fin_heureuse_uniquement BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE kdrama.kdramas
SET english_name = titre
WHERE english_name IS NULL;

-- NUMERIC(3,2) cannot represent the valid score 10.00. Rebuild the two
-- read-only views that depend on the column before widening its precision.
DROP VIEW IF EXISTS kdrama.v_kdramas_populaires;
DROP VIEW IF EXISTS kdrama.v_stats_acteurs;

ALTER TABLE kdrama.kdramas
    ALTER COLUMN note_moyenne TYPE NUMERIC(4, 2)
    USING note_moyenne::NUMERIC(4, 2);

CREATE VIEW kdrama.v_kdramas_populaires AS
SELECT k.id, k.titre, k.titre_original, k.date_diffusion, k.nb_episodes,
       k.note_moyenne, k.nb_votes,
       STRING_AGG(g.nom, ', ' ORDER BY g.nom) AS liste_genres
FROM kdrama.kdramas k
LEFT JOIN kdrama.kdrama_genres kg ON k.id = kg.kdrama_id
LEFT JOIN kdrama.genres g ON kg.genre_id = g.id
WHERE k.note_moyenne >= 7.0 AND k.nb_votes >= 100
GROUP BY k.id, k.titre, k.titre_original, k.date_diffusion,
         k.nb_episodes, k.note_moyenne, k.nb_votes;

CREATE VIEW kdrama.v_stats_acteurs AS
SELECT a.id, a.nom, a.nom_original,
       COUNT(ka.kdrama_id) AS nombre_kdramas,
       ROUND(AVG(k.note_moyenne), 2) AS note_moyenne_filmo,
       MAX(k.date_diffusion) AS derniere_apparition
FROM kdrama.acteurs a
LEFT JOIN kdrama.kdrama_acteurs ka ON a.id = ka.acteur_id
LEFT JOIN kdrama.kdramas k ON ka.kdrama_id = k.id
GROUP BY a.id, a.nom, a.nom_original;
