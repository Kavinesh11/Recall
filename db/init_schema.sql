-- Database Schema Initialization for Dash Learning System
-- Run this script to set up pgvector tables for the learning persistence layer
-- Requires: PostgreSQL with pgvector extension

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- Table: dash_learnings
-- Purpose: Store discovered error patterns and fixes as vector embeddings
-- ============================================================================
CREATE TABLE IF NOT EXISTS dash_learnings (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    error_pattern TEXT NOT NULL,
    fix_description TEXT NOT NULL,
    error_type VARCHAR(100),
    tables_involved TEXT[],
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_dash_learnings_embedding 
    ON dash_learnings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_dash_learnings_error_type 
    ON dash_learnings(error_type);

CREATE INDEX IF NOT EXISTS idx_dash_learnings_created_at 
    ON dash_learnings(created_at DESC);

-- ============================================================================
-- Table: schema_knowledge
-- Purpose: Store table schema information with semantic embeddings
-- ============================================================================
CREATE TABLE IF NOT EXISTS schema_knowledge (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL UNIQUE,
    table_description TEXT,
    columns JSONB NOT NULL DEFAULT '[]'::jsonb,
    use_cases TEXT[],
    data_quality_notes TEXT[],
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_schema_knowledge_embedding 
    ON schema_knowledge USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_schema_knowledge_table_name 
    ON schema_knowledge(table_name);

-- ============================================================================
-- Table: query_patterns
-- Purpose: Store validated SQL query patterns for reuse
-- ============================================================================
CREATE TABLE IF NOT EXISTS query_patterns (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    question TEXT NOT NULL,
    query TEXT NOT NULL,
    summary TEXT,
    tables_used TEXT[],
    data_quality_notes TEXT,
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_query_patterns_embedding 
    ON query_patterns USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_query_patterns_name 
    ON query_patterns(name);

-- ============================================================================
-- Function: update_timestamp
-- Purpose: Auto-update the updated_at column on row modification
-- ============================================================================
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_dash_learnings_timestamp ON dash_learnings;
CREATE TRIGGER trigger_dash_learnings_timestamp
    BEFORE UPDATE ON dash_learnings
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

DROP TRIGGER IF EXISTS trigger_schema_knowledge_timestamp ON schema_knowledge;
CREATE TRIGGER trigger_schema_knowledge_timestamp
    BEFORE UPDATE ON schema_knowledge
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

DROP TRIGGER IF EXISTS trigger_query_patterns_timestamp ON query_patterns;
CREATE TRIGGER trigger_query_patterns_timestamp
    BEFORE UPDATE ON query_patterns
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

-- ============================================================================
-- Function: check_learning_duplicate
-- Purpose: Check for duplicate learnings using cosine similarity
-- Returns: TRUE if a similar learning exists (similarity > 0.95)
-- ============================================================================
CREATE OR REPLACE FUNCTION check_learning_duplicate(
    p_embedding vector(1536),
    p_similarity_threshold FLOAT DEFAULT 0.95
)
RETURNS BOOLEAN AS $$
DECLARE
    v_exists BOOLEAN;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM dash_learnings
        WHERE 1 - (embedding <=> p_embedding) > p_similarity_threshold
    ) INTO v_exists;
    RETURN v_exists;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Function: search_similar_learnings
-- Purpose: Find learnings similar to the given embedding
-- ============================================================================
CREATE OR REPLACE FUNCTION search_similar_learnings(
    p_embedding vector(1536),
    p_limit INTEGER DEFAULT 5,
    p_min_similarity FLOAT DEFAULT 0.7
)
RETURNS TABLE(
    id INTEGER,
    title VARCHAR,
    error_pattern TEXT,
    fix_description TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        dl.id,
        dl.title,
        dl.error_pattern,
        dl.fix_description,
        (1 - (dl.embedding <=> p_embedding))::FLOAT as similarity
    FROM dash_learnings dl
    WHERE 1 - (dl.embedding <=> p_embedding) > p_min_similarity
    ORDER BY dl.embedding <=> p_embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Grant permissions (adjust user as needed)
-- ============================================================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dash_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO dash_user;
