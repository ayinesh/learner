# NLP Commands + Gap Analysis: Comprehensive Phased Implementation Plan

**Generated:** 2026-01-13
**Project:** AI Learning System - Personalized Learning Platform
**Sources:** `NLP_PLAN.md`, `GAP_ANALYSIS_REPORT.md`

---

## EXECUTIVE SUMMARY

This plan integrates the NLP command parsing feature with gap analysis remediation items into a coherent 5-phase implementation strategy. Each phase is independently deployable, building on the previous while maintaining backward compatibility.

**Total Estimated Effort:** 8-10 weeks
**Total Lines of Code:** ~5,090 (2,150 new + 1,240 modified + 1,700 tests)
**Risk Level:** Medium (mitigated by feature flags and fallback mechanisms)

---

## DEPENDENCY GRAPH

```
Phase 1: Infrastructure Foundation (Week 1-2)
    │
    ├── Phase 2: Database Persistence Activation (Week 2-3)
    │       │
    │       ├── Phase 3: NLP Command Integration (Week 3-5)
    │       │
    │       └── Phase 4: Content Pipeline Completion (Week 4-6) [parallel with 3]
    │               │
    └───────────────┴── Phase 5: Production Readiness (Week 6-8)
```

**Key Dependencies:**
- Phase 2 depends on Phase 1 (feature flags needed for safe rollout)
- Phase 3 depends on Phase 2 (NLP needs persistent conversation state)
- Phase 4 can run in parallel with Phase 3 after Phase 2 completes
- Phase 5 depends on Phases 3 and 4

---

## PHASE 1: INFRASTRUCTURE FOUNDATION

**Duration:** Week 1-2
**Objective:** Establish feature flags, service factory unification, and configuration management for safe feature rollout.

### Why This Phase First
Before activating database persistence or adding NLP parsing, we need infrastructure to safely toggle features and gracefully fallback if issues occur.

### Files to Create

| File | Purpose | Lines |
|------|---------|-------|
| `src/shared/feature_flags.py` | Feature flag management with env var support | ~120 |
| `src/shared/service_registry.py` | Unified service factory (in-memory ↔ DB) | ~180 |

### Files to Modify

| File | Changes | Lines |
|------|---------|-------|
| `src/shared/config.py` | Add feature flag settings to Pydantic config | +25 |
| `src/shared/exceptions.py` | Add `FeatureFlagError`, `ServiceNotAvailableError` | +30 |
| `src/modules/session/__init__.py` | Use service registry instead of direct instantiation | ~10 |
| `src/modules/content/__init__.py` | Use service registry | ~10 |
| `src/modules/assessment/__init__.py` | Use service registry | ~10 |
| `src/modules/adaptation/__init__.py` | Use service registry | ~10 |

### Implementation Details

**1. Feature Flag System (`src/shared/feature_flags.py`):**
```python
from enum import Enum
from typing import Callable, TypeVar
import os

class FeatureFlags(str, Enum):
    USE_DATABASE_PERSISTENCE = "use_database_persistence"
    ENABLE_NLP_COMMANDS = "enable_nlp_commands"
    ENABLE_REAL_EMBEDDINGS = "enable_real_embeddings"
    ENABLE_BACKGROUND_JOBS = "enable_background_jobs"

class FeatureFlagManager:
    def __init__(self):
        self._overrides: dict[str, bool] = {}

    def is_enabled(self, flag: FeatureFlags) -> bool:
        if flag.value in self._overrides:
            return self._overrides[flag.value]
        env_key = f"FF_{flag.value.upper()}"
        return os.getenv(env_key, "false").lower() == "true"

    def with_fallback(self, flag: FeatureFlags, primary: Callable, fallback: Callable):
        """Execute primary if flag enabled, fallback otherwise."""
        try:
            if self.is_enabled(flag):
                return primary()
        except Exception:
            pass  # Log and fall through
        return fallback()
```

**2. Service Registry (`src/shared/service_registry.py`):**
```python
class ServiceRegistry:
    _instance = None

    def __init__(self, flags: FeatureFlagManager):
        self._flags = flags
        self._cache = {}

    def get_session_service(self) -> ISessionService:
        if self._flags.is_enabled(FeatureFlags.USE_DATABASE_PERSISTENCE):
            from src.modules.session import get_db_session_service
            return get_db_session_service()
        from src.modules.session import get_session_service
        return get_session_service()

    # Similar methods for content, assessment, adaptation services
```

### Testing Strategy
- Unit tests for feature flag enable/disable
- Unit tests for service registry switching
- Integration test: toggle flags in running application
- Test fallback behavior when DB connection fails

### Success Criteria
1. Feature flags toggleable via environment variables
2. Service registry returns correct implementation based on flags
3. Application starts with flags in any state
4. Graceful fallback to in-memory when DB fails (with logging)

### Estimated Scope
- **New code:** ~300 lines
- **Modified code:** ~95 lines
- **Test code:** ~200 lines

---

## PHASE 2: DATABASE PERSISTENCE ACTIVATION

**Duration:** Week 2-3
**Objective:** Activate database-backed services and fix identified gaps in DB service implementations.

### Gap Analysis Items Addressed
- ✅ HIGH: "Activate database persistence" (critical)
- ✅ HIGH: "Different profile structures" in session DB service
- ✅ HIGH: "Only 2 adapters registered" in content DB service

### Blocking Dependencies
- Phase 1 complete (feature flags and service registry)

### Files to Create

| File | Purpose | Lines |
|------|---------|-------|
| `src/modules/agents/state_store_db.py` | Persistent conversation state (Redis/PostgreSQL) | ~200 |

### Files to Modify

| File | Changes | Lines |
|------|---------|-------|
| `src/modules/session/db_service.py` | Add `topics_in_progress`, align with in-memory structure | +50 |
| `src/modules/content/db_service.py` | Register all 6 adapters (YouTube, GitHub, Reddit, Twitter) | +40 |
| `src/modules/adaptation/db_service.py` | Add recent score lists for trend analysis | +80 |
| `src/modules/assessment/db_service.py` | Integrate agents instead of direct LLM calls | +60 |
| `src/modules/agents/orchestrator.py` | Use persistent state store, export `_classify_intent` | +40 |
| `src/shared/database.py` | Add connection health check with retry | +30 |

### Implementation Details

**1. Session DB Service Fixes (`src/modules/session/db_service.py`):**
```python
# Add to DatabaseSessionService
async def _ensure_profile(self, user_id: UUID) -> UserSessionProfile:
    # Add missing fields:
    # - topics_in_progress: list[UUID]
    # - preferred_consumption_ratio: float (default 0.5)
    # - gaps_identified: list[str]
```

**2. Content DB Adapter Registration (`src/modules/content/db_service.py`):**
```python
def _register_adapters(self):
    from src.modules.content.adapters import (
        ArxivAdapter, RSSAdapter, YouTubeAdapter,
        GitHubAdapter, RedditAdapter, TwitterAdapter
    )
    self._adapters = {
        SourceType.ARXIV: ArxivAdapter(),
        SourceType.BLOG: RSSAdapter(),
        SourceType.NEWSLETTER: RSSAdapter(),
        SourceType.YOUTUBE: YouTubeAdapter(),
        SourceType.GITHUB: GitHubAdapter(),
        SourceType.REDDIT: RedditAdapter(),
        SourceType.TWITTER: TwitterAdapter(),
    }
```

**3. Conversation State Persistence (`src/modules/agents/state_store_db.py`):**
```python
class DatabaseStateStore:
    async def save_conversation_state(self, user_id: UUID, state: ConversationState) -> None
    async def load_conversation_state(self, user_id: UUID) -> ConversationState | None
    async def clear_conversation_state(self, user_id: UUID) -> None
    # Uses Redis for fast access, PostgreSQL for durability
```

### Testing Strategy
- Unit tests for each DB service method
- Integration tests: in-memory vs DB service parity
- Data migration test: switch mid-session without data loss
- Performance test: DB service response times

### Success Criteria
1. All services default to DB-backed when `FF_USE_DATABASE_PERSISTENCE=true`
2. Zero data loss during feature flag toggle
3. Session plans persist across application restarts
4. Content service has all 6 adapters available
5. Conversation state persists between CLI sessions

### Estimated Scope
- **New code:** ~200 lines
- **Modified code:** ~300 lines
- **Test code:** ~400 lines

---

## PHASE 3: NLP COMMAND INTEGRATION

**Duration:** Week 3-5
**Objective:** Implement natural language command parsing as specified in NLP_PLAN.md.

### Blocking Dependencies
- Phase 2 complete (persistent conversation state required for context)

### Files to Create

| File | Purpose | Lines |
|------|---------|-------|
| `src/cli/nlp_parser.py` | NLP command parsing with security | ~350 |
| `src/cli/commands/chat.py` | Chat command group | ~250 |
| `tests/unit/test_nlp_parser.py` | NLP unit tests | ~200 |
| `tests/integration/test_nlp_flow.py` | NLP integration tests | ~150 |
| `tests/security/test_nlp_security.py` | Security tests | ~100 |

### Files to Modify

| File | Changes | Lines |
|------|---------|-------|
| `src/cli/main.py` | Register `chat_app` command group | +5 |
| `src/shared/exceptions.py` | Add `NLPParseError`, `AmbiguousCommandError` | +30 |
| `src/modules/agents/orchestrator.py` | Export `_classify_intent` for NLP reuse | +10 |

### Implementation Details

**1. NLP Command Parser (`src/cli/nlp_parser.py`):**
```python
@dataclass
class CommandIntent:
    command: str              # e.g., "learn.start"
    description: str          # Human-readable
    params: dict[str, Any]    # Validated parameters
    needs_confirmation: bool  # True for destructive actions
    command_signature: str    # e.g., "learner learn start --time 30"
    execute: Callable[[], Any]

class NLPCommandParser:
    MAX_INPUT_LENGTH = 500
    DESTRUCTIVE_COMMANDS = {"auth.logout", "learn.end", "learn.abandon"}

    def _sanitize_input(self, user_input: str) -> str:
        """Security: block shell injection, SQL injection, path traversal."""
        dangerous_patterns = [
            r'[;&|`$]',       # Shell metacharacters
            r'\.\.',          # Path traversal
            r'--',            # SQL comment
            r'DROP\s+TABLE',  # SQL injection
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                raise ValidationError("input", "Prohibited characters")
        return user_input.strip()

    async def parse_command(self, user_input: str, is_authenticated: bool) -> CommandIntent:
        sanitized = self._sanitize_input(user_input)
        intent_type, confidence, params = await self._classify_intent(sanitized, is_authenticated)
        command_builder = self._command_registry[intent_type]
        intent = command_builder(sanitized, params)
        intent.needs_confirmation = (
            intent.command in self.DESTRUCTIVE_COMMANDS or confidence < 0.8
        )
        return intent
```

**2. Chat Command Group (`src/cli/commands/chat.py`):**
```python
chat_app = typer.Typer(help="Natural language interface")

@chat_app.command("ask")
def ask(
    message: str = typer.Argument(..., help="What do you want to do?"),
    confirm: bool = typer.Option(True, "--confirm/--no-confirm"),
) -> None:
    """Execute commands using natural language.

    Examples:
      learner chat ask "start a 30 minute session"
      learner chat ask "quiz me on transformers"
    """
    parser = NLPCommandParser()
    intent = run_async(parser.parse_command(message, state.is_authenticated))

    console.print(Panel.fit(f"[cyan]Understood:[/cyan] {intent.description}"))

    if confirm and intent.needs_confirmation:
        if not Confirm.ask(f"Execute: {intent.command_signature}?"):
            raise typer.Exit(0)

    result = intent.execute()
    console.print(Panel(result.message, title="[green]Done[/green]"))

@chat_app.command("examples")
def examples() -> None:
    """Show example natural language commands."""
    # Display categorized examples
```

**3. Command Mapping Registry:**
```python
COMMAND_REGISTRY = {
    "learn.start": _build_learn_start,    # Start session
    "learn.status": _build_learn_status,  # Show status
    "learn.end": _build_learn_end,        # End session
    "quiz.start": _build_quiz_start,      # Start quiz
    "explain.start": _build_explain_start, # Feynman dialogue
    "stats.show": _build_stats_show,      # View stats
    "profile.show": _build_profile_show,  # View profile
    "content.search": _build_content_search, # Search content
    "auth.logout": _build_auth_logout,    # Logout
    "auth.whoami": _build_auth_whoami,    # Current user
}
```

### Security Measures
1. **Input Sanitization:** Max 500 chars, no shell/SQL metacharacters
2. **No Dynamic Execution:** Static command registry only (no eval/exec)
3. **Confirmation Required:** For destructive actions and low-confidence classifications
4. **Prompt Injection Protection:** Strict system prompts, output validation

### Testing Strategy
- Security tests: injection attack vectors blocked
- Unit tests: sanitization, validation, command mapping
- Integration tests: end-to-end NLP flow
- Performance: LLM classification latency < 2s

### Success Criteria
1. `learner chat ask "start a 30 minute session"` works correctly
2. All security tests pass
3. Ambiguous commands request confirmation
4. Feature flag can disable NLP without breaking CLI
5. Graceful fallback for unrecognized commands

### Estimated Scope
- **New code:** ~600 lines
- **Modified code:** ~45 lines
- **Test code:** ~450 lines

---

## PHASE 4: CONTENT PIPELINE COMPLETION

**Duration:** Week 4-6 (parallel with Phase 3)
**Objective:** Complete content pipeline with real embeddings and vector search.

### Gap Analysis Items Addressed
- ✅ HIGH: "Implement real vector embeddings"
- ✅ HIGH: "Vector search using pgvector"

### Blocking Dependencies
- Phase 2 complete (DB persistence active)
- Can run in parallel with Phase 3

### Files to Create

| File | Purpose | Lines |
|------|---------|-------|
| `src/modules/content/embeddings.py` | Embedding service abstraction | ~150 |
| `src/modules/content/vector_search.py` | pgvector search operations | ~200 |
| `migrations/003_vector_index.sql` | Create pgvector index | ~20 |

### Files to Modify

| File | Changes | Lines |
|------|---------|-------|
| `src/modules/content/db_service.py` | Integrate embedding service and vector search | +80 |
| `src/shared/config.py` | Add embedding provider config | +15 |

### Implementation Details

**1. Embedding Service (`src/modules/content/embeddings.py`):**
```python
from abc import ABC, abstractmethod

class EmbeddingService(ABC):
    @abstractmethod
    async def generate(self, text: str) -> list[float]: ...

    async def batch_generate(self, texts: list[str]) -> list[list[float]]:
        return [await self.generate(t) for t in texts]

class OpenAIEmbedding(EmbeddingService):
    """Uses text-embedding-3-small (1536 dimensions)."""
    async def generate(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000]  # Token limit
        )
        return response.data[0].embedding

class PlaceholderEmbedding(EmbeddingService):
    """MD5-based fallback for development/testing."""
    async def generate(self, text: str) -> list[float]:
        hash_val = hashlib.md5(text.encode()).hexdigest()
        embedding = [int(hash_val[i:i+2], 16) / 255.0 for i in range(0, 32, 2)]
        return embedding + [0.0] * (1536 - len(embedding))
```

**2. Vector Search (`src/modules/content/vector_search.py`):**
```python
class VectorSearchService:
    async def similarity_search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        user_id: UUID | None = None,
        source_types: list[SourceType] | None = None,
    ) -> list[tuple[UUID, float]]:
        """Returns (content_id, similarity_score) pairs."""
        query = """
            SELECT id, 1 - (embedding <=> $1::vector) as similarity
            FROM content
            WHERE ($2::uuid IS NULL OR user_id = $2)
            ORDER BY embedding <=> $1::vector
            LIMIT $3
        """
        # Execute with pgvector operator
```

**3. Migration (`migrations/003_vector_index.sql`):**
```sql
-- Create IVFFlat index for approximate nearest neighbor search
CREATE INDEX IF NOT EXISTS content_embedding_idx
ON content USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Testing Strategy
- Embedding dimension validation (1536)
- Vector search accuracy tests
- Performance benchmarks (search < 100ms)
- API cost monitoring tests

### Success Criteria
1. Real embeddings generated when `OPENAI_API_KEY` set
2. pgvector similarity search returns relevant results
3. Graceful degradation to placeholder when API key missing
4. Embedding caching prevents redundant API calls

### Estimated Scope
- **New code:** ~350 lines
- **Modified code:** ~95 lines
- **Test code:** ~300 lines
- **Migration:** ~20 lines

---

## PHASE 5: PRODUCTION READINESS

**Duration:** Week 6-8
**Objective:** Add background jobs, enhanced question types, and monitoring.

### Gap Analysis Items Addressed
- ✅ MEDIUM: "Background job infrastructure"
- ✅ MEDIUM: "Enhanced question types"
- ✅ MEDIUM: "Adaptation integration"

### Blocking Dependencies
- Phases 3 and 4 complete

### Files to Create

| File | Purpose | Lines |
|------|---------|-------|
| `src/jobs/scheduler.py` | Background job scheduler (APScheduler) | ~200 |
| `src/jobs/tasks.py` | Scheduled task definitions | ~150 |
| `src/modules/assessment/question_types.py` | Enhanced question generators | ~250 |
| `src/api/middleware/monitoring.py` | Request metrics and health | ~100 |

### Files to Modify

| File | Changes | Lines |
|------|---------|-------|
| `src/modules/assessment/service.py` | Add scenario/comparison questions | +100 |
| `src/modules/adaptation/service.py` | Integration with session planning | +80 |
| `src/modules/session/db_service.py` | Apply adaptations to plans | +50 |
| `src/api/main.py` | Add monitoring middleware | +15 |
| `docker-compose.yml` | Add Redis for job queue | +20 |

### Implementation Details

**1. Background Job Scheduler (`src/jobs/scheduler.py`):**
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

class JobScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def schedule_content_ingestion(self, interval_hours: int = 6):
        self.scheduler.add_job(
            ingest_content_task,
            'interval',
            hours=interval_hours,
            id='content_ingestion'
        )

    def schedule_token_cleanup(self, interval_hours: int = 24):
        self.scheduler.add_job(
            cleanup_expired_tokens,
            'interval',
            hours=interval_hours,
            id='token_cleanup'
        )
```

**2. Enhanced Question Types (`src/modules/assessment/question_types.py`):**
```python
class QuestionTypeGenerator:
    async def generate_scenario(self, topic: str, context: dict) -> Question:
        """Generate scenario-based question with real-world application."""
        prompt = f"""
        Create a scenario-based question about {topic}.
        The scenario should present a realistic situation requiring application of knowledge.
        """
        # LLM generation with structured output

    async def generate_comparison(self, topic_a: str, topic_b: str) -> Question:
        """Generate comparison question between two concepts."""
        # Compare and contrast style questions
```

**3. Adaptation Integration:**
```python
# In SessionService.get_session_plan()
async def get_session_plan(self, session_id: UUID) -> SessionPlan:
    plan = await self._generate_base_plan(session_id)

    # Check for pending adaptations
    adaptation = await self._adaptation_service.get_pending(user_id)
    if adaptation:
        plan = self._apply_adaptation(plan, adaptation)
        await self._adaptation_service.mark_applied(adaptation.id)

    return plan
```

### Testing Strategy
- Job scheduler unit tests
- Question type quality validation
- Adaptation integration tests
- Health endpoint tests

### Success Criteria
1. Background jobs run on schedule
2. 4+ question types available (MC, short answer, scenario, comparison)
3. Adaptations automatically applied to session plans
4. Health endpoint returns system status
5. Metrics available for monitoring

### Estimated Scope
- **New code:** ~700 lines
- **Modified code:** ~265 lines
- **Test code:** ~350 lines

---

## IMPLEMENTATION TIMELINE

```
Week 1-2: Phase 1 - Infrastructure Foundation
  └── Feature flags, service registry, testing

Week 2-3: Phase 2 - Database Persistence
  └── DB service fixes, conversation state persistence

Week 3-5: Phase 3 - NLP Commands
  └── NLP parser, security hardening, CLI integration

Week 4-6: Phase 4 - Content Pipeline (parallel with Phase 3)
  └── Real embeddings, vector search, adapters

Week 6-8: Phase 5 - Production Readiness
  └── Background jobs, enhanced questions, monitoring
```

---

## ROLLOUT STRATEGY

### Feature Flag Progression
```
Day 1:  FF_USE_DATABASE_PERSISTENCE = 10% (canary)
Day 3:  FF_USE_DATABASE_PERSISTENCE = 50%
Day 7:  FF_USE_DATABASE_PERSISTENCE = 100%

Day 8:  FF_ENABLE_NLP_COMMANDS = 10% (canary)
Day 10: FF_ENABLE_NLP_COMMANDS = 50%
Day 14: FF_ENABLE_NLP_COMMANDS = 100%

Day 15: FF_ENABLE_REAL_EMBEDDINGS = 100% (if API key set)
Day 21: FF_ENABLE_BACKGROUND_JOBS = 100%
```

### Rollback Procedures
1. **Feature Flag Rollback:** Set flag to false (immediate effect)
2. **Code Rollback:** Git revert to previous phase tag
3. **Data Rollback:** Database restore from pre-phase snapshot

---

## TOTAL ESTIMATED EFFORT

| Phase | New Code | Modified | Tests | Total |
|-------|----------|----------|-------|-------|
| Phase 1 | ~300 | ~95 | ~200 | ~595 |
| Phase 2 | ~200 | ~300 | ~400 | ~900 |
| Phase 3 | ~600 | ~45 | ~450 | ~1,095 |
| Phase 4 | ~350 | ~95 | ~300 | ~745 |
| Phase 5 | ~700 | ~265 | ~350 | ~1,315 |
| **Total** | **~2,150** | **~800** | **~1,700** | **~4,650** |

---

## RISK ASSESSMENT

| Risk | Phase | Likelihood | Impact | Mitigation |
|------|-------|------------|--------|------------|
| Service registry race conditions | 1 | Medium | Medium | Thread-safe singleton |
| DB connection timeouts | 2 | Low | Medium | Connection pool + retry |
| Prompt injection | 3 | Medium | High | Strict prompts, validation |
| Command injection | 3 | Low | Critical | Static registry (no eval) |
| Embedding API costs | 4 | Medium | Medium | Caching, batch requests |
| Job scheduler conflicts | 5 | Medium | Medium | Distributed lock (Redis) |

---

## CRITICAL FILES REFERENCE

### New Files to Create
1. `src/shared/feature_flags.py` - Feature flag management
2. `src/shared/service_registry.py` - Unified service factory
3. `src/modules/agents/state_store_db.py` - Persistent conversation state
4. `src/cli/nlp_parser.py` - NLP command parsing
5. `src/cli/commands/chat.py` - Chat command group
6. `src/modules/content/embeddings.py` - Embedding service
7. `src/modules/content/vector_search.py` - pgvector operations
8. `src/jobs/scheduler.py` - Background job scheduler
9. `src/jobs/tasks.py` - Scheduled tasks
10. `src/modules/assessment/question_types.py` - Enhanced questions

### Key Files to Modify
1. `src/shared/config.py` - Add feature flag settings
2. `src/shared/exceptions.py` - Add new exception types
3. `src/cli/main.py` - Register chat command group
4. `src/modules/agents/orchestrator.py` - Persistent state, export classify_intent
5. `src/modules/session/db_service.py` - Fix profile structure
6. `src/modules/content/db_service.py` - Register all adapters, embeddings
7. `src/modules/assessment/db_service.py` - Agent integration
8. `src/modules/adaptation/db_service.py` - Recent score lists

---

## SUCCESS METRICS

### Phase Completion Criteria
- [ ] Phase 1: Feature flags work, service registry switches correctly
- [ ] Phase 2: Data persists across restarts, all 6 adapters registered
- [ ] Phase 3: NLP commands work, all security tests pass
- [ ] Phase 4: Real embeddings generated, vector search returns results
- [ ] Phase 5: Background jobs run, 4+ question types available

### Overall Project Success
- [ ] Zero data loss during any phase transition
- [ ] No security vulnerabilities in NLP parsing
- [ ] Application maintains backward compatibility
- [ ] All feature flags can toggle without restart
- [ ] Production deployment ready by Week 8

---

**Plan Author:** Claude Code (feature-dev:code-architect)
**Review Status:** Pending user approval
