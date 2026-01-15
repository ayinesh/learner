-- Migration: Add onboarding_state column to user_learning_context
-- This column stores the conversational onboarding state for each agent

-- Add onboarding_state column to store per-agent onboarding progress
-- Format: {"curriculum": {...}, "coach": {...}, ...}
ALTER TABLE user_learning_context
ADD COLUMN IF NOT EXISTS onboarding_states JSONB DEFAULT '{}'::jsonb;

-- Add index for efficient querying
CREATE INDEX IF NOT EXISTS idx_user_learning_context_onboarding
ON user_learning_context USING gin(onboarding_states);

-- Comment for documentation
COMMENT ON COLUMN user_learning_context.onboarding_states IS
'Stores conversational onboarding state per agent. Each agent has its own state tracking which questions have been asked/answered.';
