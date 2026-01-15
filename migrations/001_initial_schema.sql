-- AI Learning System Database Schema (Neon PostgreSQL with pgvector)
-- Run via: python migrate.py

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- =====================
-- ENUM TYPES
-- =====================

CREATE TYPE source_type AS ENUM (
    'arxiv', 'twitter', 'youtube', 'newsletter', 
    'blog', 'github', 'reddit', 'discord'
);

CREATE TYPE session_status AS ENUM (
    'planned', 'in_progress', 'completed', 'abandoned'
);

CREATE TYPE session_type AS ENUM (
    'regular', 'catchup', 'drill'
);

CREATE TYPE activity_type AS ENUM (
    'content_read', 'quiz', 'feynman_dialogue', 'drill', 'reflection'
);

CREATE TYPE adaptation_type AS ENUM (
    'pace_adjustment', 'curriculum_change', 'difficulty_change', 'recovery_plan'
);

CREATE TYPE question_type AS ENUM (
    'multiple_choice', 'short_answer', 'scenario', 'comparison'
);

-- =====================
-- USER & AUTH TABLES
-- =====================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    revoked BOOLEAN DEFAULT FALSE
);

CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE NOT NULL,
    background TEXT,
    goals TEXT[] DEFAULT '{}',
    time_budget_minutes INTEGER DEFAULT 30,
    preferred_sources source_type[] DEFAULT '{}',
    timezone TEXT DEFAULT 'UTC',
    onboarding_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_source_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    source_type source_type NOT NULL,
    config JSONB NOT NULL DEFAULT '{}',
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, source_type)
);

CREATE TABLE user_learning_patterns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE NOT NULL,
    avg_session_duration FLOAT DEFAULT 0,
    preferred_time_of_day TEXT,
    completion_rate FLOAT DEFAULT 0,
    quiz_accuracy_trend FLOAT DEFAULT 0,
    feynman_score_trend FLOAT DEFAULT 0,
    days_since_last_session INTEGER DEFAULT 0,
    total_sessions INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================
-- TOPIC & KNOWLEDGE GRAPH
-- =====================

CREATE TABLE topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    prerequisites UUID[] DEFAULT '{}',
    difficulty_level INTEGER DEFAULT 3 CHECK (difficulty_level BETWEEN 1 AND 5),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE skill_components (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_topic_progress (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE NOT NULL,
    proficiency_level FLOAT DEFAULT 0 CHECK (proficiency_level BETWEEN 0 AND 1),
    last_practiced TIMESTAMPTZ,
    next_review TIMESTAMPTZ,
    practice_count INTEGER DEFAULT 0,
    interleaving_eligible BOOLEAN DEFAULT FALSE,
    ease_factor FLOAT DEFAULT 2.5,
    interval_days INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, topic_id)
);

CREATE TABLE user_skill_progress (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    skill_component_id UUID REFERENCES skill_components(id) ON DELETE CASCADE NOT NULL,
    proficiency FLOAT DEFAULT 0 CHECK (proficiency BETWEEN 0 AND 1),
    gap_identified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, skill_component_id)
);

-- =====================
-- CONTENT TABLES
-- =====================

CREATE TABLE content (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_type source_type NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    raw_content TEXT,
    processed_content TEXT,
    summary TEXT,
    embedding vector(1536),  -- pgvector for semantic search
    topics UUID[] DEFAULT '{}',
    difficulty_level INTEGER DEFAULT 3 CHECK (difficulty_level BETWEEN 1 AND 5),
    importance_score FLOAT DEFAULT 0.5,
    author TEXT,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE TABLE user_content_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    content_id UUID REFERENCES content(id) ON DELETE CASCADE NOT NULL,
    presented_at TIMESTAMPTZ DEFAULT NOW(),
    completed BOOLEAN DEFAULT FALSE,
    time_spent_seconds INTEGER DEFAULT 0,
    relevance_feedback INTEGER CHECK (relevance_feedback BETWEEN 1 AND 5),
    notes TEXT,
    UNIQUE(user_id, content_id)
);

-- =====================
-- SESSION TABLES
-- =====================

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    session_type session_type DEFAULT 'regular',
    status session_status DEFAULT 'planned',
    planned_duration_minutes INTEGER NOT NULL,
    actual_duration_minutes INTEGER,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE session_activities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE NOT NULL,
    activity_type activity_type NOT NULL,
    topic_id UUID REFERENCES topics(id) ON DELETE SET NULL,
    content_id UUID REFERENCES content(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    performance_data JSONB DEFAULT '{}'
);

-- =====================
-- ASSESSMENT TABLES
-- =====================

CREATE TABLE quizzes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    topic_ids UUID[] NOT NULL,
    questions JSONB NOT NULL,
    is_spaced_repetition BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE quiz_attempts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quiz_id UUID REFERENCES quizzes(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    answers JSONB NOT NULL,
    score FLOAT CHECK (score BETWEEN 0 AND 1),
    time_taken_seconds INTEGER,
    gaps_identified UUID[] DEFAULT '{}',
    attempted_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE feynman_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE NOT NULL,
    dialogue_history JSONB DEFAULT '[]',
    status TEXT DEFAULT 'active',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE feynman_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    feynman_session_id UUID REFERENCES feynman_sessions(id) ON DELETE CASCADE NOT NULL,
    completeness_score FLOAT CHECK (completeness_score BETWEEN 0 AND 1),
    accuracy_score FLOAT CHECK (accuracy_score BETWEEN 0 AND 1),
    simplicity_score FLOAT CHECK (simplicity_score BETWEEN 0 AND 1),
    overall_score FLOAT CHECK (overall_score BETWEEN 0 AND 1),
    gaps JSONB DEFAULT '[]',
    strengths JSONB DEFAULT '[]',
    suggestions JSONB DEFAULT '[]',
    evaluated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================
-- ADAPTATION TABLES
-- =====================

CREATE TABLE adaptation_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    adaptation_type adaptation_type NOT NULL,
    trigger_reason TEXT NOT NULL,
    old_value JSONB,
    new_value JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================
-- INDEXES
-- =====================

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
CREATE INDEX idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX idx_user_source_configs_user_id ON user_source_configs(user_id);
CREATE INDEX idx_user_learning_patterns_user_id ON user_learning_patterns(user_id);
CREATE INDEX idx_user_topic_progress_user_id ON user_topic_progress(user_id);
CREATE INDEX idx_user_topic_progress_topic_id ON user_topic_progress(topic_id);
CREATE INDEX idx_user_topic_progress_next_review ON user_topic_progress(next_review);
CREATE INDEX idx_content_source_type ON content(source_type);
CREATE INDEX idx_content_created_at ON content(created_at DESC);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_started_at ON sessions(started_at DESC);
CREATE INDEX idx_session_activities_session_id ON session_activities(session_id);
CREATE INDEX idx_quizzes_user_id ON quizzes(user_id);
CREATE INDEX idx_quiz_attempts_user_id ON quiz_attempts(user_id);
CREATE INDEX idx_feynman_sessions_user_id ON feynman_sessions(user_id);

-- Vector similarity index (IVFFlat for approximate nearest neighbor)
-- Creates index after some data exists for better performance
-- Run manually after inserting initial content:
-- CREATE INDEX idx_content_embedding ON content USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- =====================
-- FUNCTIONS & TRIGGERS
-- =====================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_user_source_configs_updated_at
    BEFORE UPDATE ON user_source_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_user_topic_progress_updated_at
    BEFORE UPDATE ON user_topic_progress
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_user_skill_progress_updated_at
    BEFORE UPDATE ON user_skill_progress
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_profiles (user_id)
    VALUES (NEW.id);
    
    INSERT INTO user_learning_patterns (user_id)
    VALUES (NEW.id);
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER on_user_created
    AFTER INSERT ON users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS void AS $$
BEGIN
    DELETE FROM refresh_tokens
    WHERE expires_at < NOW() OR revoked = TRUE;
END;
$$ LANGUAGE plpgsql;

-- =====================
-- HELPER FUNCTIONS FOR VECTOR SEARCH
-- =====================

-- Function to find similar content by embedding
CREATE OR REPLACE FUNCTION find_similar_content(
    query_embedding vector(1536),
    limit_count INTEGER DEFAULT 10
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
    ORDER BY c.embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;
