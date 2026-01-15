-- Vector Index Migration for Content Embeddings
-- This migration creates an IVFFlat index on the content.embedding column
-- for efficient approximate nearest neighbor (ANN) search using pgvector.
--
-- Prerequisites:
-- - pgvector extension must be installed (already done in 001_initial_schema.sql)
-- - Content table must have some rows with embeddings for optimal performance
--
-- Performance Notes:
-- - IVFFlat index divides the vector space into 'lists' (clusters)
-- - lists=100 is appropriate for datasets with 10k-100k vectors
-- - For smaller datasets (<10k), use lists=10-50
-- - For larger datasets (>100k), use lists=1000+
-- - Index build time scales with data size
--
-- Usage:
-- Apply via: python migrate.py
-- Or manually: psql $DATABASE_URL -f migrations/003_vector_index.sql

-- =====================
-- VECTOR INDEX CREATION
-- =====================

-- Create IVFFlat index for cosine similarity search
-- The index uses vector_cosine_ops for cosine distance optimization
-- This enables fast nearest neighbor queries using the <=> operator
CREATE INDEX IF NOT EXISTS content_embedding_idx
ON content USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Note: Index creation can take several minutes on large datasets
-- Progress can be monitored using:
-- SELECT * FROM pg_stat_progress_create_index;

-- =====================
-- INDEX VERIFICATION
-- =====================

-- Verify index was created successfully
DO $$
DECLARE
    index_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE tablename = 'content'
        AND indexname = 'content_embedding_idx'
    ) INTO index_exists;

    IF index_exists THEN
        RAISE NOTICE 'Vector index created successfully: content_embedding_idx';
    ELSE
        RAISE WARNING 'Vector index creation may have failed';
    END IF;
END $$;

-- =====================
-- HELPER FUNCTIONS UPDATE
-- =====================

-- Update the find_similar_content function to use the index
-- This replaces the function from 001_initial_schema.sql with an optimized version
CREATE OR REPLACE FUNCTION find_similar_content(
    query_embedding vector(1536),
    limit_count INTEGER DEFAULT 10,
    min_similarity FLOAT DEFAULT 0.0
)
RETURNS TABLE (
    content_id UUID,
    title TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.title,
        1 - (c.embedding <=> query_embedding) as similarity
    FROM content c
    WHERE c.embedding IS NOT NULL
    AND c.processed_at IS NOT NULL
    AND (1 - (c.embedding <=> query_embedding)) >= min_similarity
    ORDER BY c.embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Add function to search by topic with vector similarity
CREATE OR REPLACE FUNCTION find_similar_content_by_topic(
    query_embedding vector(1536),
    topic_ids UUID[],
    limit_count INTEGER DEFAULT 10,
    min_similarity FLOAT DEFAULT 0.5
)
RETURNS TABLE (
    content_id UUID,
    title TEXT,
    similarity FLOAT,
    matching_topics INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.title,
        1 - (c.embedding <=> query_embedding) as similarity,
        (SELECT COUNT(*) FROM unnest(c.topics) t WHERE t = ANY(topic_ids))::INTEGER as matching_topics
    FROM content c
    WHERE c.embedding IS NOT NULL
    AND c.processed_at IS NOT NULL
    AND c.topics && topic_ids  -- Array overlap operator
    AND (1 - (c.embedding <=> query_embedding)) >= min_similarity
    ORDER BY c.embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- =====================
-- MAINTENANCE FUNCTIONS
-- =====================

-- Function to rebuild the vector index (useful after bulk inserts)
CREATE OR REPLACE FUNCTION rebuild_vector_index()
RETURNS void AS $$
BEGIN
    -- Drop and recreate index
    DROP INDEX IF EXISTS content_embedding_idx;

    -- Recreate with optimal lists parameter based on current data size
    EXECUTE format(
        'CREATE INDEX content_embedding_idx ON content USING ivfflat (embedding vector_cosine_ops) WITH (lists = %s)',
        GREATEST(10, LEAST(1000, (SELECT COUNT(*) FROM content WHERE embedding IS NOT NULL) / 100))
    );

    RAISE NOTICE 'Vector index rebuilt successfully';
END;
$$ LANGUAGE plpgsql;

-- Function to get index statistics
CREATE OR REPLACE FUNCTION get_vector_index_stats()
RETURNS TABLE (
    total_content BIGINT,
    indexed_content BIGINT,
    index_size TEXT,
    index_bloat_ratio FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        (SELECT COUNT(*) FROM content WHERE processed_at IS NOT NULL)::BIGINT as total_content,
        (SELECT COUNT(*) FROM content WHERE embedding IS NOT NULL)::BIGINT as indexed_content,
        pg_size_pretty(pg_relation_size('content_embedding_idx'))::TEXT as index_size,
        CASE
            WHEN pg_relation_size('content_embedding_idx') > 0
            THEN (pg_relation_size('content') / pg_relation_size('content_embedding_idx')::FLOAT)
            ELSE 0.0
        END as index_bloat_ratio;
END;
$$ LANGUAGE plpgsql;

-- =====================
-- PERFORMANCE NOTES
-- =====================

-- For optimal vector search performance:
-- 1. Ensure content.embedding column has values before creating index
-- 2. Use ANALYZE content after bulk inserts to update statistics
-- 3. Monitor query performance with EXPLAIN ANALYZE
-- 4. Adjust lists parameter based on dataset size
-- 5. Consider rebuilding index after significant data changes

-- Example query to check if index is being used:
-- EXPLAIN ANALYZE
-- SELECT id, 1 - (embedding <=> '[0.1,0.2,...]') as similarity
-- FROM content
-- WHERE embedding IS NOT NULL
-- ORDER BY embedding <=> '[0.1,0.2,...]'
-- LIMIT 10;

-- Expected output should show "Index Scan using content_embedding_idx"
