-- ===========================================================================
-- drama_sentiments_schema.sql — Table pour stocker les sentiments des dramas
--
-- Table d'analyse de l'opinion des spectateurs sur les dramas.
-- La source de vérité pour les informations du drama reste kdrama.kdramas.
-- Le scraper ne stocke donc PAS total_episodes ici.
-- ===========================================================================

SET search_path TO kdrama, public;

CREATE TABLE IF NOT EXISTS kdrama.drama_sentiments (
    id                          SERIAL PRIMARY KEY,
    drama_id                    INTEGER NOT NULL UNIQUE REFERENCES kdrama.kdramas(id) ON DELETE CASCADE,

    -- Classification du type d'ending
    ending_type                 VARCHAR(50),
    ending_confidence           FLOAT CHECK (ending_confidence >= 0 AND ending_confidence <= 1),

    -- Score de sentiment global
    sentiment_score             FLOAT CHECK (sentiment_score >= -1 AND sentiment_score <= 1),
    sentiment_summary           TEXT,

    -- Statut du drama
    is_ongoing                  BOOLEAN DEFAULT FALSE,
    is_completed                BOOLEAN DEFAULT FALSE,

    -- Métadonnées de scraping
    scraped_date                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_urls                 TEXT[],
    data_quality_score          FLOAT CHECK (data_quality_score >= 0 AND data_quality_score <= 1),

    -- Détails supplémentaires
    top_comments                TEXT,
    notable_triggers            TEXT[],
    viewer_consensus            TEXT
);

-- If the table already existed with the old column, remove it.
-- Safe to run repeatedly.
ALTER TABLE kdrama.drama_sentiments
    DROP COLUMN IF EXISTS total_episodes;

CREATE INDEX IF NOT EXISTS idx_drama_sentiments_drama_id
    ON kdrama.drama_sentiments(drama_id);

CREATE INDEX IF NOT EXISTS idx_drama_sentiments_ending_type
    ON kdrama.drama_sentiments(ending_type);

CREATE INDEX IF NOT EXISTS idx_drama_sentiments_sentiment_score
    ON kdrama.drama_sentiments(sentiment_score);

COMMENT ON TABLE kdrama.drama_sentiments IS
    'Sentiments et analyses des dramas - rempli par le scraper';

COMMENT ON COLUMN kdrama.drama_sentiments.ending_type IS
    'Type d''ending: happy, sad, bittersweet, ongoing, unknown';

COMMENT ON COLUMN kdrama.drama_sentiments.ending_confidence IS
    'Confiance dans la classification (0-1)';

COMMENT ON COLUMN kdrama.drama_sentiments.sentiment_score IS
    'Score de sentiment agrégé (-1 à 1)';

-- ===========================================================================
-- Fin du script — drama_sentiments_schema.sql
-- ===========================================================================
