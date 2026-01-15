-- Security Constraints Migration
-- Adds database-level constraints for data integrity and race condition prevention

-- =====================
-- SESSION RACE CONDITION FIX
-- =====================
-- Prevent multiple active sessions per user at the database level
-- This is a partial unique index that only applies when status = 'in_progress'
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_active_session
ON sessions(user_id)
WHERE status = 'in_progress';

-- =====================
-- PASSWORD RESET TOKEN INDEXES
-- =====================
-- Faster lookup for valid (unused, not expired) password reset tokens
CREATE INDEX IF NOT EXISTS idx_reset_tokens_valid
ON password_reset_tokens(user_id, token_hash)
WHERE used = FALSE;

-- Index for cleanup queries
CREATE INDEX IF NOT EXISTS idx_reset_tokens_expired
ON password_reset_tokens(expires_at)
WHERE used = FALSE;

-- =====================
-- REFRESH TOKEN INDEXES
-- =====================
-- Faster lookup for valid (not revoked, not expired) refresh tokens
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_valid
ON refresh_tokens(token_hash)
WHERE revoked = FALSE;

-- Index for cleanup queries
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expired
ON refresh_tokens(expires_at)
WHERE revoked = FALSE;

-- =====================
-- SESSION ACTIVITY INDEXES
-- =====================
-- Faster lookup for session activities
CREATE INDEX IF NOT EXISTS idx_session_activities_session
ON session_activities(session_id);

-- =====================
-- CONTENT INTERACTION INDEXES
-- =====================
-- Faster lookup for user content interactions (used in relevance scoring)
CREATE INDEX IF NOT EXISTS idx_user_content_interactions_user
ON user_content_interactions(user_id)
WHERE completed = TRUE;

-- =====================
-- USER TOPIC PROGRESS INDEXES
-- =====================
-- Faster lookup for user topic progress (used in relevance scoring)
CREATE INDEX IF NOT EXISTS idx_user_topic_progress_user
ON user_topic_progress(user_id);

-- =====================
-- COMMENTS
-- =====================
COMMENT ON INDEX idx_user_active_session IS 'Prevents race condition allowing multiple active sessions per user';
COMMENT ON INDEX idx_reset_tokens_valid IS 'Optimizes password reset token lookup for validation';
COMMENT ON INDEX idx_refresh_tokens_valid IS 'Optimizes refresh token lookup for validation';
