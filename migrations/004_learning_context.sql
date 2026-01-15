-- Migration: 004_learning_context.sql
-- Description: Create user_learning_context table for shared agent context
-- This enables agents to share awareness of user goals, focus areas, and progress

-- Create the user_learning_context table
CREATE TABLE IF NOT EXISTS user_learning_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign key to users table
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE NOT NULL,

    -- Primary learning goal (extracted from conversations)
    -- e.g., "become an ML expert", "learn Python for data science"
    primary_goal TEXT,

    -- Current focus area within the goal
    -- e.g., "math foundations", "linear algebra"
    current_focus TEXT,

    -- Learning path stages with progress
    -- Format: [{"topic": "math", "status": "in_progress", "progress": 0.5, "milestone": "complete basics", "parent_goal": "ML"}]
    learning_path JSONB DEFAULT '[]'::jsonb,

    -- User preferences discovered from conversation
    -- Format: {"learning_style": "hands-on", "pace": "moderate", "explanation_depth": "detailed"}
    preferences JSONB DEFAULT '{}'::jsonb,

    -- Recent topics discussed (for continuity)
    recent_topics TEXT[] DEFAULT ARRAY[]::TEXT[],

    -- Knowledge gaps identified by agents
    identified_gaps TEXT[] DEFAULT ARRAY[]::TEXT[],

    -- User's stated constraints
    -- Format: {"time_per_day_minutes": 30, "deadline": "3 months", "background": "beginner"}
    constraints JSONB DEFAULT '{}'::jsonb,

    -- Proficiency levels by topic (0.0 to 1.0)
    -- Format: {"linear_algebra": 0.3, "python_basics": 0.7}
    proficiency_levels JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookups by user_id
CREATE INDEX IF NOT EXISTS idx_user_learning_context_user_id
    ON user_learning_context(user_id);

-- Index for finding users with specific goals (for analytics/debugging)
CREATE INDEX IF NOT EXISTS idx_user_learning_context_primary_goal
    ON user_learning_context(primary_goal)
    WHERE primary_goal IS NOT NULL;

-- Trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_learning_context_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_learning_context_timestamp ON user_learning_context;
CREATE TRIGGER trigger_update_learning_context_timestamp
    BEFORE UPDATE ON user_learning_context
    FOR EACH ROW
    EXECUTE FUNCTION update_learning_context_timestamp();

-- Comment on table
COMMENT ON TABLE user_learning_context IS
    'Stores shared learning context accessible by all AI agents. Enables agents to work together toward user goals.';
