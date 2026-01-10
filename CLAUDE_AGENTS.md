# Claude Code Agent Setup for Parallel Development

This guide explains how to set up multiple Claude Code agents to build different modules of the AI Learning System simultaneously.

## Overview

The project is architected with clean module boundaries and defined interfaces, enabling parallel development. Each module can be built independently as long as it adheres to its interface contract.

## Module Dependency Graph

```
                    ┌─────────┐
                    │   llm   │ (no dependencies - build first)
                    └────┬────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌─────────┐    ┌──────────┐    ┌──────────┐
    │  auth   │    │  agents  │    │ content  │
    └────┬────┘    └────┬─────┘    └────┬─────┘
         │              │               │
         ▼              │               │
    ┌─────────┐         │               │
    │  user   │         │               │
    └────┬────┘         │               │
         │              │               │
         └──────────────┼───────────────┘
                        │
                        ▼
               ┌────────────────┐
               │   assessment   │
               └───────┬────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
         ▼             ▼             ▼
    ┌─────────┐  ┌──────────┐  ┌────────────┐
    │ session │  │adaptation│  │    cli     │
    └─────────┘  └──────────┘  └────────────┘
```

## Recommended Agent Assignments

### For 2-3 Parallel Agents

**Agent A: Core Infrastructure**
```
Modules: auth, user, shared
Priority: High (blocks other work)
```

**Agent B: Intelligence Layer**  
```
Modules: llm, agents, assessment
Priority: High (llm blocks many modules)
```

**Agent C: Content & Session**
```
Modules: content, session, cli
Priority: Medium (can start after interfaces defined)
```

## Setting Up Claude Code Agents

### Step 1: Clone the Repository

Each agent instance needs its own working copy:

```bash
# Agent A
cd ~/projects
git clone <repo-url> ai-learning-agent-a
cd ai-learning-agent-a
git checkout -b feature/auth-user

# Agent B  
cd ~/projects
git clone <repo-url> ai-learning-agent-b
cd ai-learning-agent-b
git checkout -b feature/llm-agents

# Agent C
cd ~/projects
git clone <repo-url> ai-learning-agent-c
cd ai-learning-agent-c
git checkout -b feature/content-session
```

### Step 2: Create CLAUDE.md Files

Each agent needs a CLAUDE.md file in its working directory with specific instructions.

**Agent A - CLAUDE.md:**
```markdown
# Agent A: Core Infrastructure

## Your Modules
- src/modules/auth/
- src/modules/user/
- src/shared/

## Your Task
Implement the auth and user modules following the interfaces defined in:
- src/modules/auth/interface.py
- src/modules/user/interface.py

## Implementation Order
1. Complete src/shared/ utilities (already partially done)
2. Complete auth/service.py - JWT auth with bcrypt (stub already exists)
3. Create SQLAlchemy models in auth/models.py and user/models.py
4. Implement user/service.py using SQLAlchemy
5. Write tests in tests/unit/test_auth.py and tests/unit/test_user.py

## Interface Contracts
You MUST implement all methods defined in the interface files.
Do NOT modify the interface files without coordination.

## Key Files to Create
- src/modules/auth/models.py (SQLAlchemy models for users, refresh_tokens)
- src/modules/auth/schemas.py (Pydantic schemas)
- src/modules/user/models.py (SQLAlchemy models)
- src/modules/user/service.py
- src/modules/user/schemas.py
- tests/unit/test_auth.py
- tests/unit/test_user.py

## Commands
- `make install` - Install dependencies
- `make test-unit` - Run unit tests
- `make lint` - Check code style

## Notes
- Use async SQLAlchemy from src/shared/database.py
- Use Redis from src/shared/database.py for token blacklisting (optional)
- Auth uses JWT (pyjwt) + bcrypt - see auth/service.py stub
- Follow existing code patterns in src/shared/
- All database operations should be async
```

**Agent B - CLAUDE.md:**
```markdown
# Agent B: Intelligence Layer

## Your Modules
- src/modules/llm/
- src/modules/agents/
- src/modules/assessment/
- prompts/

## Your Task
Implement the LLM wrapper, agent definitions, and assessment system.

## Implementation Order
1. Complete src/modules/llm/service.py (already started)
2. Create prompt templates in prompts/
3. Implement individual agents in src/modules/agents/
4. Implement assessment/service.py
5. Write tests

## Interface Contracts
Follow interfaces in:
- src/modules/llm/service.py (already has implementation)
- src/modules/agents/interface.py
- src/modules/assessment/interface.py

## Key Files to Create
- prompts/socratic/confused_student.txt
- prompts/assessment/quiz_generation.txt
- prompts/assessment/feynman_evaluation.txt
- prompts/coach/session_opening.txt
- src/modules/agents/orchestrator.py
- src/modules/agents/socratic.py
- src/modules/agents/assessment_agent.py
- src/modules/agents/coach.py
- src/modules/assessment/service.py
- src/modules/assessment/quiz.py
- src/modules/assessment/feynman.py

## Prompt Template Format
Use this format for prompt files:
```
---SYSTEM---
Your system prompt here
---USER---
Your user prompt template with {{variables}}
---VARIABLES---
variable1, variable2
```

## Commands
- `make install` - Install dependencies
- `make test-unit` - Run unit tests
```

**Agent C - CLAUDE.md:**
```markdown
# Agent C: Content & Session

## Your Modules
- src/modules/content/
- src/modules/session/
- src/cli/

## Your Task
Implement content ingestion, session management, and CLI commands.

## Implementation Order
1. Implement content source adapters (start with RSS/arXiv)
2. Implement content processing pipeline
3. Implement session/service.py
4. Complete CLI commands in src/cli/main.py
5. Write tests

## Interface Contracts
Follow interfaces in:
- src/modules/content/interface.py
- src/modules/session/interface.py

## Key Files to Create
- src/modules/content/models.py (SQLAlchemy models)
- src/modules/content/service.py
- src/modules/content/adapters/base.py
- src/modules/content/adapters/arxiv.py
- src/modules/content/adapters/rss.py
- src/modules/content/processing.py
- src/modules/session/models.py
- src/modules/session/service.py
- src/modules/session/planner.py
- tests/unit/test_content.py
- tests/unit/test_session.py

## Dependencies
This module depends on:
- llm module (for summarization, embeddings)
- user module (for relevance scoring)
- assessment module (for session planning)

Use the INTERFACES only - don't import concrete implementations.
Mock dependencies in tests.

## Commands
- `make install` - Install dependencies
- `make test-unit` - Run unit tests
- `make dev` - Test CLI

## Notes
- Use async SQLAlchemy from src/shared/database.py
- For vector search, use pgvector with SQLAlchemy
- Redis can be used for caching frequent queries
```

### Step 3: Launch Claude Code Agents

Open separate terminal windows/tabs for each agent:

```bash
# Terminal 1 - Agent A
cd ~/projects/ai-learning-agent-a
claude

# Terminal 2 - Agent B
cd ~/projects/ai-learning-agent-b
claude

# Terminal 3 - Agent C
cd ~/projects/ai-learning-agent-c
claude
```

### Step 4: Initial Prompts for Each Agent

**Prompt for Agent A:**
```
Read the CLAUDE.md file and the interface files for auth and user modules.
Then implement the auth module service following the interface exactly.
Start with the AuthService class in src/modules/auth/service.py.
Use Supabase Auth for all authentication operations.
```

**Prompt for Agent B:**
```
Read the CLAUDE.md file. Your first task is to create the prompt templates.
Start by creating prompts/socratic/confused_student.txt with the system
prompt for the Socratic agent (the confused student for Feynman dialogues).
The agent should be curious, ask naive questions, and probe deeply.
```

**Prompt for Agent C:**
```
Read the CLAUDE.md file and src/modules/content/interface.py.
Start by implementing the base SourceAdapter class and the arXiv adapter.
The arXiv adapter should fetch papers from specified categories.
```

## Coordination Rules

### 1. Interface Changes
If you need to change an interface:
1. STOP and create a PR with just the interface change
2. Get it merged to main
3. All agents pull the updated interface
4. Continue implementation

### 2. Shared Code Changes
Changes to `src/shared/` must be coordinated:
1. One agent makes the change
2. Commit and push to a shared branch
3. Other agents pull before continuing

### 3. Merge Strategy
```bash
# Each agent regularly pulls from main
git fetch origin
git rebase origin/main

# When module is complete
git push origin feature/your-branch
# Create PR, get review, merge
```

### 4. Testing Before Merge
Before creating a PR:
```bash
make lint      # Must pass
make typecheck # Must pass  
make test-unit # Must pass
```

## Integration Points

When modules need to communicate:

### Content → LLM
Content module needs LLM for summarization:
```python
# In content/service.py
from src.modules.llm.service import get_llm_service

class ContentService:
    def __init__(self):
        self.llm = get_llm_service()
    
    async def summarize(self, text: str) -> str:
        response = await self.llm.complete(
            prompt=f"Summarize this content:\n\n{text}",
            system_prompt="You are a concise summarizer."
        )
        return response.content
```

### Session → Assessment
Session module needs assessment for quizzes:
```python
# In session/service.py
from src.modules.assessment.interface import IAssessmentService

class SessionService:
    def __init__(self, assessment_service: IAssessmentService):
        self.assessment = assessment_service
```

### CLI → All Services
CLI imports and uses all services:
```python
# In cli/main.py
from src.modules.auth.service import get_auth_service
from src.modules.session.service import get_session_service
# etc.
```

## Troubleshooting

### Merge Conflicts
If you get conflicts in interface files:
1. Accept the main branch version
2. Re-implement your changes to match new interface
3. Never force-push to main

### Import Errors
If imports fail:
1. Check that `__init__.py` exists in all directories
2. Run `poetry install` to ensure dependencies
3. Check circular import issues

### Test Failures After Merge
1. Pull latest main
2. Run `make install` (dependencies may have changed)
3. Check if interfaces changed
4. Update your implementation to match

## Daily Workflow

1. **Start of day:**
   ```bash
   git fetch origin
   git rebase origin/main
   make install
   make test
   ```

2. **During development:**
   - Commit frequently
   - Run tests after each significant change
   - Push to your feature branch regularly

3. **End of day:**
   ```bash
   git push origin feature/your-branch
   ```
   Create PR if module is complete.

## Communication Channels

Since agents can't talk to each other directly, use:
1. **Git commits** - Clear messages about what changed
2. **PR descriptions** - Document interface impacts
3. **Code comments** - Mark `# TODO: Needs Agent X to complete Y`
