"""Application-wide constants.

This module centralizes magic numbers and configuration values that are
used across multiple modules. Values that need to be configurable at
runtime should go in config.py instead.
"""

# ===================
# Session Limits
# ===================

# Valid time budget range for learning sessions (in minutes)
MIN_SESSION_DURATION_MINUTES = 5
MAX_SESSION_DURATION_MINUTES = 480  # 8 hours

# Default session duration when not specified
DEFAULT_SESSION_DURATION_MINUTES = 30

# Session inactivity timeout (in seconds)
SESSION_INACTIVITY_TIMEOUT_SECONDS = 3600  # 1 hour


# ===================
# Assessment Constants
# ===================

# Difficulty level range (1 = easiest, 5 = hardest)
MIN_DIFFICULTY_LEVEL = 1
MAX_DIFFICULTY_LEVEL = 5
DEFAULT_DIFFICULTY_LEVEL = 3

# Quiz question counts
MIN_QUIZ_QUESTIONS = 1
MAX_QUIZ_QUESTIONS = 50
DEFAULT_QUIZ_QUESTIONS = 5

# Score validation range (0.0 = 0%, 1.0 = 100%)
MIN_SCORE = 0.0
MAX_SCORE = 1.0

# Passing score threshold
DEFAULT_PASSING_SCORE = 0.7


# ===================
# Content Constants
# ===================

# Maximum content title length
MAX_CONTENT_TITLE_LENGTH = 200

# Maximum content body length (in characters)
MAX_CONTENT_BODY_LENGTH = 50000

# Embedding dimensions (OpenAI text-embedding-3-small)
EMBEDDING_DIMENSIONS = 1536

# Vector search result limits
DEFAULT_SEARCH_RESULTS = 10
MAX_SEARCH_RESULTS = 100


# ===================
# User Input Limits
# ===================

# Email validation
MAX_EMAIL_LENGTH = 254  # RFC 5321

# Password requirements
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

# Username limits (if implemented)
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 50


# ===================
# Rate Limiting
# ===================

# Default rate limit window (in seconds)
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60

# Cleanup settings
RATE_LIMIT_CLEANUP_PROBABILITY = 0.001  # 0.1% chance per request
RATE_LIMIT_CLEANUP_MAX_AGE_SECONDS = 3600  # 1 hour


# ===================
# Caching
# ===================

# Cache TTL defaults (in seconds)
CACHE_TTL_SHORT = 300  # 5 minutes
CACHE_TTL_MEDIUM = 3600  # 1 hour
CACHE_TTL_LONG = 86400  # 24 hours

# Conversation state TTL
CONVERSATION_STATE_TTL_SECONDS = 3600  # 1 hour


# ===================
# Token/Retry Limits
# ===================

# Password reset token expiration (in hours)
PASSWORD_RESET_TOKEN_EXPIRATION_HOURS = 1

# Token cleanup retention period (in days)
TOKEN_CLEANUP_RETENTION_DAYS = 7

# Database health check retries
DB_HEALTH_CHECK_MAX_RETRIES = 3
DB_HEALTH_CHECK_RETRY_DELAY_SECONDS = 1.0

# API startup retries
STARTUP_MAX_RETRIES = 5
STARTUP_RETRY_DELAY_SECONDS = 2.0


# ===================
# Logging
# ===================

# Request ID format validation pattern
REQUEST_ID_PATTERN = r'^[a-zA-Z0-9\-_]{1,64}$'

# Maximum log message length to prevent log injection
MAX_LOG_MESSAGE_LENGTH = 10000


# ===================
# Security
# ===================

# HSTS max age (in seconds) - 1 year
HSTS_MAX_AGE_SECONDS = 31536000

# CORS preflight cache (in seconds)
CORS_PREFLIGHT_MAX_AGE_SECONDS = 600  # 10 minutes

# Distributed lock settings
DISTRIBUTED_LOCK_TTL_SECONDS = 30
DISTRIBUTED_LOCK_RETRY_DELAY_SECONDS = 0.1
DISTRIBUTED_LOCK_MAX_RETRIES = 50


# ===================
# Conversation Context
# ===================

# Number of recent exchanges to include in LLM context (sliding window)
# Higher = more context but more tokens; Lower = less tokens but more amnesia
CONTEXT_HISTORY_WINDOW_SIZE = 10

# Maximum characters for context summary injection
CONTEXT_SUMMARY_MAX_CHARS = 500
