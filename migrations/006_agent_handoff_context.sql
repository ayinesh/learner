-- Migration: 006_agent_handoff_context.sql
-- Description: Add agent handoff context and cross-agent action log
-- This enables smooth context transfer between agents and tracks what each agent did

-- Add handoff_context column to store context passed between agents
ALTER TABLE user_learning_context
ADD COLUMN IF NOT EXISTS handoff_context JSONB DEFAULT '{}'::jsonb;

-- Add agent_action_log column to track what each agent did
-- Format: [{"agent": "coach", "action": "set_goal", "details": {...}, "timestamp": "..."}]
ALTER TABLE user_learning_context
ADD COLUMN IF NOT EXISTS agent_action_log JSONB DEFAULT '[]'::jsonb;

-- Add last_agent_summary column for quick access to what previous agent accomplished
ALTER TABLE user_learning_context
ADD COLUMN IF NOT EXISTS last_agent_summary JSONB DEFAULT NULL;

-- Add consolidated_onboarding column for shared onboarding answers
-- All agents can read from this instead of each having separate onboarding
ALTER TABLE user_learning_context
ADD COLUMN IF NOT EXISTS consolidated_onboarding JSONB DEFAULT '{}'::jsonb;

-- Add agent_discoveries column for agent-specific discoveries that should be shared
-- Format: {"misconceptions": [...], "learning_observations": [...], "suggested_approaches": [...]}
ALTER TABLE user_learning_context
ADD COLUMN IF NOT EXISTS agent_discoveries JSONB DEFAULT '{}'::jsonb;

-- Index for efficient handoff context lookups
CREATE INDEX IF NOT EXISTS idx_user_learning_context_handoff
    ON user_learning_context USING gin (handoff_context);

-- Index for action log queries (e.g., "what did assessment agent do?")
CREATE INDEX IF NOT EXISTS idx_user_learning_context_action_log
    ON user_learning_context USING gin (agent_action_log);

-- Comment on new columns
COMMENT ON COLUMN user_learning_context.handoff_context IS
    'Context passed from one agent to another during transitions. Includes summary of work done, discoveries, and suggested next steps.';

COMMENT ON COLUMN user_learning_context.agent_action_log IS
    'Chronological log of actions taken by each agent. Enables cross-agent coordination and prevents duplicate work.';

COMMENT ON COLUMN user_learning_context.last_agent_summary IS
    'Summary from the most recent agent interaction. Quick access for the next agent to understand what just happened.';

COMMENT ON COLUMN user_learning_context.consolidated_onboarding IS
    'Shared onboarding answers accessible by all agents. Prevents asking duplicate questions across agents.';

COMMENT ON COLUMN user_learning_context.agent_discoveries IS
    'Discoveries made by agents that should be shared (misconceptions, learning style observations, etc).';
