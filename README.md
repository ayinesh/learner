# AI Learning System

A hyper-personal AI learning system that guides you through structured learning journeys in the AI ecosystem. Built on principles from Ultralearning (Scott Young), Learning How to Learn (Barbara Oakley), and the Feynman Technique.

## Features

- **Personalized Learning Paths**: Adapts to your background, goals, and available time
- **50/50 Production/Consumption**: Balances reading with active practice
- **Feynman Dialogues**: AI "confused student" that probes your understanding
- **Retrieval Practice**: Spaced repetition quizzes that strengthen memory
- **Semantic Content Discovery**: pgvector-powered similarity search finds relevant content
- **Adaptive System**: Adjusts pace, difficulty, and curriculum based on your progress
- **Multi-Source Content**: Aggregates from arXiv, Twitter, YouTube, newsletters, blogs, GitHub, Reddit, Discord

## Tech Stack

- **Backend**: Python 3.11+ with FastAPI
- **CLI**: Typer with Rich
- **Database**: Neon PostgreSQL (serverless) with pgvector
- **Cache**: Redis (Upstash recommended for production)
- **Auth**: JWT (bcrypt + pyjwt)
- **LLM**: Anthropic Claude API
- **Vector Search**: pgvector for semantic similarity

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry (or pip)
- Neon account (free)
- Anthropic API key

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd ai-learning-system

# Install dependencies
pip install sqlalchemy asyncpg python-dotenv bcrypt pyjwt anthropic

# Copy environment template
cp .env.example .env

# Edit .env with your credentials (see Neon Setup below)
```

### Neon Setup

1. **Create Neon Account**
   - Go to [neon.tech](https://neon.tech)
   - Sign up (free tier includes 512MB storage)

2. **Create New Project**
   - Click "New Project"
   - Name: `ai-learning-system`
   - Region: Choose closest to you
   - Click "Create Project"

3. **Get Connection String**
   - After project creation, you'll see the connection string
   - Or go to Dashboard → Connection Details
   - Copy the connection string
   - Add `+asyncpg` after `postgresql`:
     ```
     postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
     ```

4. **Update .env**
   ```
   DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

5. **Run Migration**
   ```bash
   python migrate.py
   ```

### Redis Setup (Optional for MVP)

For production, use Upstash Redis:
1. Go to [upstash.com](https://upstash.com)
2. Create free Redis database
3. Copy the connection string to `.env`

For local development:
```bash
# Docker
docker run -d --name redis -p 6379:6379 redis:alpine

# Or skip Redis for MVP (caching disabled)
REDIS_URL=redis://localhost:6379
```

### Usage

```bash
# See all commands
python -m src.cli.main --help

# Start a learning session
python -m src.cli.main start

# Take a quiz
python -m src.cli.main quiz

# Feynman dialogue on a topic
python -m src.cli.main explain "attention mechanisms"

# View progress
python -m src.cli.main progress
```

## Project Structure

```
ai-learning-system/
├── src/
│   ├── modules/
│   │   ├── auth/         # JWT Authentication
│   │   ├── user/         # User profiles & preferences
│   │   ├── content/      # Content ingestion & vector search
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

### Parallel Development

This project is designed for parallel development using multiple Claude Code agents. See `CLAUDE_AGENTS.md` for setup instructions.

### Adding a New Content Source

1. Create adapter in `src/modules/content/adapters/`
2. Implement `SourceAdapter` interface
3. Register in `ContentService`
4. Add configuration schema

### Vector Search

Content embeddings are stored using pgvector:

```python
# Store embedding
content.embedding = await llm_service.get_embedding(content.summary)

# Find similar content
similar = await session.execute(
    select(Content)
    .order_by(Content.embedding.cosine_distance(query_embedding))
    .limit(10)
)
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `DATABASE_URL` | Yes | Neon PostgreSQL URL (with +asyncpg and sslmode=require) |
| `REDIS_URL` | No | Redis URL (optional for MVP) |
| `JWT_SECRET_KEY` | Yes | Secret for JWT signing |
| `LOG_LEVEL` | No | Logging level (default: INFO) |
| `DEFAULT_SESSION_MINUTES` | No | Default session length (default: 30) |

### Content Sources

Configure sources during onboarding or via CLI:

- **arXiv**: Paper categories (cs.AI, cs.LG, etc.)
- **Twitter/X**: Accounts or lists to follow
- **YouTube**: Channels to monitor
- **RSS**: Newsletter and blog feeds
- **GitHub**: Repos or topics to track
- **Reddit**: Subreddits
- **Discord**: Server webhooks

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

## License

MIT
