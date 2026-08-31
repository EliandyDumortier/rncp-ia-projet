-- ===========================================================================
-- drama_sentiments_schema.sql — Table pour stocker les sentiments des dramas
--
-- Ajoute une table pour stocker les analyses de sentiments, les types
-- d'endings et les statuts d'un drama (en cours, terminé, etc.)
--
-- Cette table est remplie par le scraper drama_sentiment_scraper.py
-- ===========================================================================

SET search_path TO kdrama, public;

-- ---------------------------------------------------------------------------
-- Table: drama_sentiments (sentiments et endings des dramas)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS kdrama.drama_sentiments (
    id                          SERIAL PRIMARY KEY,
    drama_id                    INTEGER NOT NULL UNIQUE REFERENCES kdrama.kdramas(id) ON DELETE CASCADE,

    -- Classification du type d'ending
    ending_type                 VARCHAR(50),  -- 'happy', 'sad', 'bittersweet', 'ongoing', 'unknown'
    ending_confidence           FLOAT CHECK (ending_confidence >= 0 AND ending_confidence <= 1),  -- 0-1

    -- Score de sentiment global (-1 = très négatif, 1 = très positif)
    sentiment_score             FLOAT CHECK (sentiment_score >= -1 AND sentiment_score <= 1),
    sentiment_summary           TEXT,  -- résumé des sentiments (ex: "mostly positive, some sad elements")

    -- Statut du drama
    is_ongoing                  BOOLEAN DEFAULT FALSE,
    is_completed                BOOLEAN DEFAULT FALSE,
    total_episodes              INTEGER,

    -- Métadonnées de scraping
    scraped_date                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_urls                 TEXT[],  -- URLs d'où les données ont été extraites
    data_quality_score          FLOAT CHECK (data_quality_score >= 0 AND data_quality_score <= 1),  -- confiance globale

    -- Détails supplémentaires
    top_comments                TEXT,  -- Les commentaires les plus pertinents
    notable_triggers            TEXT[],  -- Éléments qui pourraient déranger (death, abuse, etc.)
    viewer_consensus            TEXT  -- Consensus général des spectateurs
);

CREATE INDEX IF NOT EXISTS idx_drama_sentiments_drama_id ON kdrama.drama_sentiments(drama_id);
CREATE INDEX IF NOT EXISTS idx_drama_sentiments_ending_type ON kdrama.drama_sentiments(ending_type);
CREATE INDEX IF NOT EXISTS idx_drama_sentiments_sentiment_score ON kdrama.drama_sentiments(sentiment_score);

COMMENT ON TABLE kdrama.drama_sentiments IS 'Sentiments et analyses des dramas - rempli par le scraper';
COMMENT ON COLUMN kdrama.drama_sentiments.ending_type IS 'Type d''ending: happy, sad, bittersweet, ongoing, unknown';
COMMENT ON COLUMN kdrama.drama_sentiments.ending_confidence IS 'Confiance dans la classification (0-1)';
COMMENT ON COLUMN kdrama.drama_sentiments.sentiment_score IS 'Score de sentiment agrégé (-1 à 1)';

-- ===========================================================================
-- Fin du script — drama_sentiments_schema.sql
-- ===========================================================================
