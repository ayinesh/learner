# AI Learning System

A hyper-personal AI learning system that guides you through structured learning journeys in the AI ecosystem. Built on principles from Ultralearning (Scott Young), Learning How to Learn (Barbara Oakley), and the Feynman Technique.

## Features

- **Personalized Learning Paths**: Adapts to your background, goals, and available time
- **50/50 Production/Consumption**: Balances reading with active practice
- **Feynman Dialogues**: AI "confused student" that probes your understanding
- **Retrieval Practice**: Spaced repetition quizzes that strengthen memory
- **Adaptive System**: Adjusts pace, difficulty, and curriculum based on your progress
- **Multi-Source Content**: Aggregates from arXiv, Twitter, YouTube, newsletters, blogs, GitHub, Reddit, Discord

## Tech Stack

- **Backend**: Python 3.11+ with FastAPI
- **CLI**: Typer with Rich
- **Database**: Railway PostgreSQL with pgvector
- **Cache/Sessions**: Railway Redis
- **Auth**: JWT (bcrypt + pyjwt)
- **LLM**: Anthropic Claude API

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry
- Railway account (or local Docker for PostgreSQL + Redis)

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd ai-learning-system

# Install dependencies
make install

# Copy environment template
cp .env.example .env

# Edit .env with your credentials (see Railway Setup below)
```

### Railway Setup

1. **Create Railway Project**
   - Go to [railway.app](https://railway.app)
   - Create new project
   - Add PostgreSQL service
   - Add Redis service

2. **Get Connection Strings**
   - Click on PostgreSQL → Variables → Copy `DATABASE_URL`
   - Click on Redis → Variables → Copy `REDIS_URL`
   - Update `.env`:
     ```
     DATABASE_URL=postgresql+asyncpg://...  # Add +asyncpg after postgresql
     REDIS_URL=redis://...
     ```

3. **Run Database Migration**
   - In Railway, click PostgreSQL → Data → SQL Editor
   - Copy and run contents of `migrations/001_initial_schema.sql`

4. **Enable pgvector Extension**
   - The migration script includes `CREATE EXTENSION vector`
   - If it fails, contact Railway support to enable pgvector

5. **Generate JWT Secret**
   ```bash
   openssl rand -hex 32
   ```
   Add to `.env` as `JWT_SECRET_KEY`

### Local Development (Alternative)

If you prefer local development:

```bash
# Start PostgreSQL with pgvector
docker run -d \
  --name postgres-vectors \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=ai_learning \
  -p 5432:5432 \
  ankane/pgvector

# Start Redis
docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:alpine

# Update .env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/ai_learning
REDIS_URL=redis://localhost:6379

# Run migration
psql -h localhost -U postgres -d ai_learning -f migrations/001_initial_schema.sql
```

### Usage

```bash
# See all commands
learn --help

# Start a learning session
learn start

# Start with specific time
learn start --time 30

# Take a quiz
learn quiz

# Feynman dialogue on a topic
learn explain "attention mechanisms"

# View progress
learn progress

# Login/Register
learn auth login
learn auth register
```

## Project Structure

```
ai-learning-system/
├── src/
│   ├── modules/
│   │   ├── auth/         # JWT Authentication
│   │   ├── user/         # User profiles & preferences
│   │   ├── content/      # Content ingestion & processing
│   │   ├── session/      # Learning session management
│   │   ├── assessment/   # Quizzes & Feynman dialogues
│   │   ├── adaptation/   # Learning pattern analysis
│   │   ├── agents/       # AI agent definitions
│   │   └── llm/          # Anthropic API wrapper
│   ├── cli/              # Command-line interface
│   ├── api/              # FastAPI endpoints
│   └── shared/           # Common utilities
├── prompts/              # LLM prompt templates
├── migrations/           # Database migrations
├── tests/
│   ├── unit/
│   └── integration/
└── docs/
```

## Development

### Commands

```bash
make install      # Install dependencies
make dev          # Run CLI in dev mode
make api          # Run API server
make test         # Run all tests
make test-unit    # Run unit tests only
make lint         # Check code style
make format       # Format code
make typecheck    # Run type checker
make check        # Run all checks
```

### Parallel Development

This project is designed for parallel development using multiple Claude Code agents. See `CLAUDE_AGENTS.md` for setup instructions.

### Adding a New Content Source

1. Create adapter in `src/modules/content/adapters/`
2. Implement `SourceAdapter` interface
3. Register in `ContentService`
4. Add configuration schema

### Adding a New Agent

1. Create agent class in `src/modules/agents/`
2. Inherit from `BaseAgent`
3. Define system prompt
4. Register in `AgentOrchestrator`
5. Create prompt template in `prompts/`

## Architecture

### Learning Science Integration

| System Component | Ultralearning | Learning How to Learn |
|------------------|---------------|----------------------|
| Onboarding | Metalearning | Chunking strategy |
| Session Start | Focus | Focused mode |
| Content Delivery | Directness | Chunking |
| Practice | Drill, Retrieval | Retrieval, Interleaving |
| Feynman Dialogue | Intuition, Feedback | Illusion avoidance |
| Between Sessions | Retention | Spaced repetition |

### Agent Architecture

The system uses specialized AI agents orchestrated to appear as one coherent assistant:

- **Curriculum Agent**: Plans learning paths
- **Socratic Agent**: "Confused student" for Feynman dialogues  
- **Assessment Agent**: Generates quizzes, evaluates understanding
- **Coach Agent**: Motivation, session management
- **Scout Agent**: Monitors AI ecosystem for relevant content
- **Drill Sergeant Agent**: Targets weak spots with practice

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `DATABASE_URL` | Yes | Railway PostgreSQL URL (with +asyncpg) |
| `REDIS_URL` | Yes | Railway Redis URL |
| `JWT_SECRET_KEY` | Yes | Secret for JWT signing |
| `LOG_LEVEL` | No | Logging level (default: INFO) |
| `DEFAULT_SESSION_MINUTES` | No | Default session length (default: 30) |

### Content Sources

Configure sources during onboarding or via `learn sources --add`:

- **arXiv**: Paper categories (cs.AI, cs.LG, etc.)
- **Twitter/X**: Accounts or lists to follow
- **YouTube**: Channels to monitor
- **RSS**: Newsletter and blog feeds
- **GitHub**: Repos or topics to track
- **Reddit**: Subreddits
- **Discord**: Server webhooks

## Deployment

### Railway Deployment

1. Connect your GitHub repo to Railway
2. Railway auto-detects Python and creates a service
3. Add environment variables in Railway dashboard
4. Deploy!

```bash
# railway.json (optional, for custom config)
{
  "build": {
    "builder": "nixpacks"
  },
  "deploy": {
    "startCommand": "poetry run uvicorn src.api.main:app --host 0.0.0.0 --port $PORT"
  }
}
```

## Contributing

1. Read `CLAUDE_AGENTS.md` for development workflow
2. Follow interface contracts in `*/interface.py`
3. Write tests for new functionality
4. Run `make check` before submitting PR

## License

MIT
