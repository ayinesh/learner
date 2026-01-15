# Learner - Comprehensive User Guide

A hyper-personalized AI learning system that guides you through structured learning journeys. Built on principles from Ultralearning (Scott Young), Learning How to Learn (Barbara Oakley), and the Feynman Technique.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Who Should Use This Application](#2-who-should-use-this-application)
3. [Architecture Overview](#3-architecture-overview)
4. [Installation & Setup](#4-installation--setup)
5. [Configuration Reference](#5-configuration-reference)
6. [Using the CLI](#6-using-the-cli)
7. [Using the REST API](#7-using-the-rest-api)
8. [The AI Agent System](#8-the-ai-agent-system)
9. [Learning Features](#9-learning-features)
10. [How It Works - Technical Deep Dive](#10-how-it-works---technical-deep-dive)
11. [Deployment](#11-deployment)
12. [Troubleshooting](#12-troubleshooting)
13. [Quick Reference](#13-quick-reference)

---

## 1. Introduction

### What Is This App?

**Learner** is a personalized learning platform that helps you master AI and machine learning concepts through evidence-based learning techniques. Think of it as having a personal tutor that:

- Creates a custom study plan based on your goals and background
- Finds articles, videos, and papers that match your skill level
- Quizzes you to verify understanding (not just recognition)
- Makes you explain concepts in simple words (Feynman technique)
- Uses spaced repetition so you remember long-term
- Motivates you with streaks and progress tracking

### Why Is It "Smart"?

Unlike traditional learning platforms, this system uses **6 specialized AI agents** that work together:

| Agent | Role |
|-------|------|
| **Coach** | Motivates you, manages sessions, tracks streaks |
| **Curriculum** | Plans your learning path based on goals |
| **Scout** | Finds relevant content from multiple sources |
| **Assessment** | Creates adaptive quizzes to test understanding |
| **Socratic** | Plays a "confused student" for Feynman dialogues |
| **Drill Sergeant** | Targets weak areas with focused practice |

### Core Features

- **Personalized Learning Paths**: Adapts to your background, goals, and available time
- **50/50 Production/Consumption**: Balances reading with active practice
- **Feynman Dialogues**: AI "confused student" that probes your understanding
- **Retrieval Practice**: Spaced repetition quizzes strengthen memory
- **Semantic Content Discovery**: Vector search finds conceptually related content
- **Adaptive System**: Adjusts pace and difficulty based on performance
- **Multi-Source Content**: Aggregates from arXiv, YouTube, blogs, GitHub, Reddit

### Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11+ with FastAPI |
| CLI | Typer with Rich |
| Database | PostgreSQL (Neon serverless) with pgvector |
| Cache | Redis (Upstash for production) |
| Authentication | JWT (bcrypt + pyjwt) |
| AI | Anthropic Claude API |
| Vector Search | pgvector for semantic similarity |

---

## 2. Who Should Use This Application

### Target Audience

| User Type | Use Case |
|-----------|----------|
| **AI/ML Learners** | Learning artificial intelligence, machine learning, or data science |
| **Self-directed Learners** | Prefer structured self-study over traditional courses |
| **Professionals Upskilling** | Engineers or analysts expanding into AI/ML |
| **Students** | CS students supplementing academic learning |
| **Interview Preparation** | Systematic study of ML concepts with assessment |
| **Researchers** | Breaking down arXiv papers with Feynman dialogues |

### Ideal Use Cases

1. **Daily Learning Practice**: 30-60 minute focused sessions on AI topics
2. **Interview Preparation**: Systematic study with quizzes and assessments
3. **Research Paper Understanding**: Deep dive into papers with Feynman technique
4. **Skill Gap Identification**: Finding weak areas through targeted practice
5. **Long-term Knowledge Retention**: Spaced repetition prevents forgetting

### Problems It Solves

| Traditional Learning Problem | How This System Solves It |
|------------------------------|---------------------------|
| Passive consumption (watching tutorials) | Enforces 50/50 balance between consumption and production |
| Illusion of competence | AI "confused student" dialogues expose knowledge gaps |
| Information overload | Aggregates and curates content from multiple sources |
| One-size-fits-all pacing | Adapts difficulty and pace based on performance |
| Poor retention | Implements spaced repetition for long-term memory |

---

## 3. Architecture Overview

### The Big Picture

```
+---------------------------------------------------------------------+
|                              USER                                     |
|                                |                                      |
|               +----------------+----------------+                      |
|               v                                v                      |
|         +---------+                    +-------------+                |
|         |   CLI   |                    |  REST API   |                |
|         |(Terminal)|                    | (Web/Apps)  |                |
|         +----+----+                    +------+------+                |
|              |                                |                        |
|              +----------------+---------------+                        |
|                               v                                        |
|              +-------------------------------+                         |
|              |        BUSINESS LOGIC         |                         |
|              |                               |                         |
|              |  +-------------------------+  |                         |
|              |  | AUTH MODULE             |  |  (handles login)        |
|              |  +-------------------------+  |                         |
|              |  | SESSION MODULE          |  |  (learning sessions)    |
|              |  +-------------------------+  |                         |
|              |  | CONTENT MODULE          |  |  (study materials)      |
|              |  +-------------------------+  |                         |
|              |  | ASSESSMENT MODULE       |  |  (quizzes/Feynman)      |
|              |  +-------------------------+  |                         |
|              |  | AGENTS MODULE           |  |  (6 AI helpers)         |
|              |  +-------------------------+  |                         |
|              +---------------+---------------+                         |
|                              v                                         |
|              +-------------------------------+                         |
|              |          DATABASE             |                         |
|              |        (PostgreSQL)           |                         |
|              |   Users, Sessions, Quizzes,   |                         |
|              |   Content, Progress, etc.     |                         |
|              +-------------------------------+                         |
+---------------------------------------------------------------------+
```

### Project Structure

```
src/
├── api/                    # REST API (for web/mobile apps)
│   ├── main.py            # Starts the API server
│   ├── routers/           # URL endpoint definitions
│   │   ├── auth.py        # Login/logout endpoints
│   │   ├── sessions.py    # Learning session endpoints
│   │   ├── content.py     # Content search endpoints
│   │   └── assessments.py # Quiz endpoints
│   ├── middleware/        # Security and request processing
│   │   ├── rate_limit.py  # Rate limiting (brute force protection)
│   │   ├── request_size.py # Request body size limits
│   │   ├── security_headers.py # HSTS, CSP, etc.
│   │   └── logging.py     # Request logging
│   └── schemas/           # Data validation rules
│
├── cli/                    # Terminal Interface
│   ├── main.py            # Main command definitions
│   ├── nlp_parser.py      # Natural language understanding
│   ├── state.py           # Secure token storage
│   └── commands/          # Command groups
│
├── modules/                # Business Logic
│   ├── auth/              # JWT authentication
│   ├── user/              # User profiles
│   ├── session/           # Learning sessions
│   ├── content/           # Study materials & vector search
│   ├── assessment/        # Quizzes and tests
│   ├── adaptation/        # Difficulty adjustment
│   ├── agents/            # 6 AI helpers
│   └── llm/               # Anthropic API wrapper
│
└── shared/                 # Common utilities
    ├── config.py          # Settings from environment
    ├── database.py        # Database connection
    ├── audit.py           # Security event logging
    └── constants.py       # Application constants
```

### Learning Science Integration

| System Component | Ultralearning Principle | Learning How to Learn |
|------------------|------------------------|----------------------|
| Onboarding | Metalearning | Chunking strategy |
| Session Start | Focus | Focused mode |
| Content Delivery | Directness | Chunking |
| Practice | Drill, Retrieval | Retrieval, Interleaving |
| Feynman Dialogue | Intuition, Feedback | Illusion avoidance |
| Between Sessions | Retention | Spaced repetition |

---

## 4. Installation & Setup

### System Requirements

| Requirement | Specification |
|-------------|---------------|
| **Python** | 3.11 or higher |
| **OS** | Windows, macOS, or Linux |
| **Memory** | 4GB RAM minimum |
| **Storage** | 500MB for application |

### Step 1: Clone and Install

```bash
# Clone repository
git clone <repository-url>
cd Learner

# Install dependencies
pip install -r requirements.txt

# Or using Poetry
poetry install
```

### Step 2: Set Up Database (Neon PostgreSQL)

1. **Create a Neon Account**
   - Go to [neon.tech](https://neon.tech)
   - Sign up for free (512MB storage included)

2. **Create a Project**
   - Click "New Project"
   - Name: `ai-learning-system`
   - Choose your region
   - Click "Create Project"

3. **Get Connection String**
   - Go to Dashboard → Connection Details
   - Copy the connection string
   - **Important**: Add `+asyncpg` after `postgresql` and `?sslmode=require` at the end

   ```
   postgresql+asyncpg://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
   ```

### Step 3: Set Up Redis (Optional)

For production, use Upstash Redis:
1. Go to [upstash.com](https://upstash.com)
2. Create a free Redis database
3. Copy the connection string

For local development:
```bash
# Docker
docker run -d --name redis -p 6379:6379 redis:alpine

# Or skip Redis for development (caching disabled)
REDIS_URL=redis://localhost:6379
```

### Step 4: Configure Environment

```bash
# Create environment file
cp .env.prod.example .env

# Edit with your credentials
```

**Minimum required `.env` configuration:**

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
JWT_SECRET_KEY=your-secret-key-here

# Generate JWT secret (PowerShell)
[System.Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))

# Generate JWT secret (Linux/macOS)
openssl rand -hex 32
```

### Step 5: Run Database Migrations

```bash
python migrate.py
```

Expected output:
```
==================================================
AI Learning System - Database Migration
==================================================

Connecting to: postgresql+asyncpg://...
Found 76 SQL statements to execute

  [1/76] ✓ CREATE EXTENSION IF NOT EXISTS "uuid-ossp"...
  ...
  [76/76] ✓ Done

✓ All statements executed successfully!
Found 15 tables.
```

### Step 6: Verify Installation

```bash
# Test CLI
python -m src.cli.main --help

# Test API
uvicorn src.api.main:app --reload --port 8000
# Then visit http://localhost:8000/docs
```

---

## 5. Configuration Reference

All configuration is done through environment variables. Create a `.env` file in the project root.

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key from [console.anthropic.com](https://console.anthropic.com) | `sk-ant-api03-xxx` |
| `DATABASE_URL` | Neon PostgreSQL URL (must include `+asyncpg` and `?sslmode=require`) | `postgresql+asyncpg://...` |
| `JWT_SECRET_KEY` | Secret for signing JWT tokens (generate with `openssl rand -hex 32`) | `8vMrIaZbx7...` |

### Authentication Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRATION_HOURS` | `24` | Access token lifetime |
| `JWT_REFRESH_EXPIRATION_DAYS` | `7` | Refresh token lifetime |

### Database Pool Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_POOL_SIZE` | `5` | Number of persistent connections |
| `DB_MAX_OVERFLOW` | `10` | Additional connections when pool is full |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait for connection |
| `DB_POOL_RECYCLE` | `3600` | Recycle connections after (seconds) |

### CORS Settings (Production)

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `` | Comma-separated allowed origins (e.g., `https://app.example.com,https://www.example.com`) |

**Security Note**: In production, you MUST set `CORS_ORIGINS` to your frontend domain(s). Without it, browsers cannot access the API.

### Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | `development`, `staging`, or `production` |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `API_HOST` | `0.0.0.0` | API bind address |
| `API_PORT` | `8000` | API port |

### LLM Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_MODEL` | `claude-sonnet-4-20250514` | Claude model to use |
| `MAX_TOKENS` | `4096` | Maximum response tokens |
| `TEMPERATURE` | `0.7` | Response randomness (0-1) |

### Optional Content Source API Keys

| Variable | Provider | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | OpenAI | Text embeddings |
| `TWITTER_BEARER_TOKEN` | Twitter/X | Content ingestion |
| `YOUTUBE_API_KEY` | Google Cloud | Video content |
| `GITHUB_TOKEN` | GitHub | Code examples |
| `REDDIT_CLIENT_ID` | Reddit | Discussions |
| `REDDIT_CLIENT_SECRET` | Reddit | Discussions |

### Optional Services

| Variable | Provider | Purpose |
|----------|----------|---------|
| `REDIS_URL` | Upstash/Local | Caching & rate limiting |

### Complete Example `.env`

```bash
# ===================
# Required
# ===================
ANTHROPIC_API_KEY=sk-ant-api03-your-key
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
JWT_SECRET_KEY=your-32-char-secret-here

# ===================
# Production Settings
# ===================
ENVIRONMENT=production
LOG_LEVEL=INFO
CORS_ORIGINS=https://myapp.com,https://www.myapp.com

# ===================
# Database Pool
# ===================
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600

# ===================
# Redis (Optional)
# ===================
REDIS_URL=rediss://default:xxx@xxx.upstash.io:6379

# ===================
# LLM Settings
# ===================
DEFAULT_MODEL=claude-sonnet-4-20250514
MAX_TOKENS=4096
TEMPERATURE=0.7
```

---

## 6. Using the CLI

The CLI provides a terminal interface for all learning features.

### Getting Started

```bash
# See all commands
python -m src.cli.main --help

# Or use the short alias
learner --help
```

### Authentication Commands

```bash
# Register a new account
learner auth register

# Login to your account
learner auth login

# Check current user
learner auth whoami

# Logout
learner auth logout

# Refresh tokens
learner auth refresh

# Change password
learner auth change-password
```

**Password Requirements** (enforced on registration and password change):
- Minimum 8 characters, maximum 128
- At least one uppercase letter (A-Z)
- At least one lowercase letter (a-z)
- At least one digit (0-9)
- At least one special character (!@#$%^&*(),.?":{}|<>-_=+[]\\;'`~)
- Cannot be a common password (password, 12345678, etc.)

### Learning Session Commands

```bash
# Start a learning session (default 30 minutes)
learner start

# Start with custom duration
learner start --time 45

# Start specific session type
learner start --type drill      # Focused practice on weak areas
learner start --type catchup    # Recovery after missed days

# Check current session status
learner status

# End current session
learner learn end
```

**Session Types:**

| Type | Description |
|------|-------------|
| `regular` | Balanced learning (50% reading, 50% practice) |
| `drill` | Focused practice on weak areas |
| `catchup` | Recovery after missed days |

### Assessment Commands

```bash
# Take a quiz
learner quiz
learner quiz --topic "transformers"
learner quiz --topic "attention" --count 5

# Feynman dialogue (explain a concept)
learner explain "attention mechanisms"
```

### Progress & Statistics

```bash
# View overall statistics
learner stats summary

# View learning streak
learner stats streak

# View topic mastery levels
learner stats topics

# View progress over time
learner stats progress
```

### Profile Commands

```bash
# Complete onboarding questionnaire
learner profile onboarding

# Update learning preferences
learner profile update

# View current profile
learner profile show
```

### Natural Language Commands

The CLI understands natural language! You can type conversational commands:

```bash
learner chat "quiz me on transformers"
learner chat "start a 45 minute session"
learner chat "explain attention mechanisms"
learner chat "show my progress"
```

---

## 7. Using the REST API

### Starting the API Server

```bash
# Development mode (with auto-reload)
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### API Documentation

Once running, access interactive documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Authentication Endpoints (`/auth`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create new account |
| POST | `/auth/login` | Get access tokens |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Revoke refresh token |
| POST | `/auth/password/change` | Change password |
| POST | `/auth/password/reset-request` | Request password reset |
| POST | `/auth/password/reset` | Complete password reset |
| GET | `/auth/me` | Get current user info |

### Session Endpoints (`/sessions`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sessions` | Start new session |
| GET | `/sessions/current` | Get active session |
| GET | `/sessions/{id}` | Get session details |
| DELETE | `/sessions/{id}` | End session |
| GET | `/sessions/history` | Get session history |
| GET | `/sessions/streak` | Get learning streak |

### Assessment Endpoints (`/assessments`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/assessments/quiz` | Generate quiz |
| POST | `/assessments/quiz/{id}/submit` | Submit answers |
| POST | `/assessments/feynman` | Start Feynman dialogue |
| POST | `/assessments/feynman/{id}/message` | Continue dialogue |
| GET | `/assessments/reviews` | Get items due for review |

### Content Endpoints (`/content`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/content/feed` | Get personalized content |
| GET | `/content/search` | Search content |
| GET | `/content/{id}` | Get content details |
| POST | `/content/{id}/feedback` | Submit feedback |
| POST | `/content/ingest` | Ingest new content (admin) |

### User Endpoints (`/users`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users/profile` | Get user profile |
| PUT | `/users/profile` | Update profile |
| POST | `/users/profile/onboarding` | Complete onboarding |

### Example API Usage

**Register a new account:**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'
```

**Login:**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'
```

**Start a learning session:**
```bash
curl -X POST http://localhost:8000/sessions \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "available_minutes": 45,
    "session_type": "regular"
  }'
```

**Generate a quiz:**
```bash
curl -X POST http://localhost:8000/assessments/quiz \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "attention mechanisms",
    "num_questions": 5
  }'
```

### Rate Limiting

The API implements rate limiting to prevent abuse:

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/auth/register` | 3 requests | per hour |
| `/auth/login` | 5 requests | per 5 minutes |
| `/auth/refresh` | 10 requests | per hour |
| `/auth/password/reset-request` | 2 requests | per hour |
| `/content/*` | 100 requests | per minute |
| `/sessions/*` | 50 requests | per minute |

Exceeding limits returns HTTP 429 with `Retry-After` header.

### Request Size Limits

| Endpoint | Max Body Size |
|----------|---------------|
| `/content/ingest` | 10 MB |
| All other endpoints | 1 MB |

---

## 8. The AI Agent System

The application uses 6 specialized AI agents powered by Claude, coordinated by an Orchestrator.

### The Orchestrator

The Orchestrator routes user requests to the appropriate agent:

```
User: "Start a session"
         |
         v
   +-------------+
   | ORCHESTRATOR | --> "This needs Coach agent"
   +------+------+
          |
          v
   +-------------+
   |    COACH    | --> "Welcome back! Let's plan..."
   +-------------+
```

### Agent 1: Coach Agent

**Role**: Motivation and session management

**Responsibilities**:
- Opens sessions with personalized greetings
- Tracks and celebrates learning streaks
- Closes sessions with summaries
- Provides encouragement and recovery plans

**Example Output**:
```
"Welcome back! You're on a 5-day streak!
Today we'll continue with attention mechanisms.
Your last quiz score was 80% - great progress!"
```

### Agent 2: Curriculum Agent

**Role**: Learning path planning

**Responsibilities**:
- Creates structured learning roadmaps
- Recommends next topics based on progress
- Balances new material with review
- Considers goals and time constraints

**Example Output**:
```
Week 1: Attention Basics
  - Day 1-2: What is attention?
  - Day 3-4: Query-Key-Value mechanics

Week 2: Transformer Architecture
  - Day 1-2: Encoder structure
  - Day 3-4: Decoder structure
```

### Agent 3: Scout Agent

**Role**: Content discovery

**Responsibilities**:
- Searches for relevant articles, videos, papers
- Matches content to user's skill level
- Filters based on preferences
- Provides summaries

### Agent 4: Assessment Agent

**Role**: Quiz generation and evaluation

**Responsibilities**:
- Generates questions based on learned material
- Adjusts difficulty based on performance
- Identifies knowledge gaps
- Implements spaced repetition scheduling

**Question Types**:
- Multiple choice
- Short answer
- Scenario-based ("What would happen if...")
- Comparison ("How is X different from Y?")

### Agent 5: Socratic Agent

**Role**: Feynman technique "confused student"

**Responsibilities**:
- Pretends to be a smart but uninformed student
- Asks probing questions to test understanding
- Challenges vague explanations
- Exposes gaps in knowledge

**Example Dialogue**:
```
You: "Attention helps the model focus on relevant parts."

AI: "Wait, I'm confused. How does a computer 'focus'?
    Does it have eyes?"

You: "Well, it assigns weights to different inputs..."

AI: "Weights? Like gym weights? What determines these weights?"
```

### Agent 6: Drill Sergeant Agent

**Role**: Targeted skill practice

**Responsibilities**:
- Identifies struggling areas
- Creates focused exercises
- Pushes improvement on weak points
- Tracks skill development

### How Agents Collaborate

Here's a typical session showing agent teamwork:

```
1. You start session
   └→ ORCHESTRATOR routes to COACH
   └→ COACH: "Welcome! Let's see what to learn..."

2. COACH asks CURRICULUM: "What's next?"
   └→ CURRICULUM: "Based on progress, learn transformers"

3. CURRICULUM asks SCOUT: "Find transformer content"
   └→ SCOUT: "Here's a video and article"

4. You finish reading...
   └→ COACH: "Time for a quiz!"
   └→ ASSESSMENT creates questions

5. You score 60%...
   └→ ASSESSMENT identifies gap: "encoder structure"
   └→ DRILL SERGEANT: "Let's practice encoders"

6. You finish session
   └→ COACH: "Great work! Summary: learned transformers,
              need more encoder practice. 5-day streak!"
```

---

## 9. Learning Features

### Adaptive Learning Sessions

Sessions balance consumption (reading/watching) with production (practice/testing):

| Phase | Time | Activities |
|-------|------|------------|
| **Consumption** | 50% | Reading articles, watching videos |
| **Production** | 50% | Quizzes, Feynman dialogues, exercises |

### Session Lifecycle

```
+----------+     +-------------+     +-----------+
| PLANNED  | --> | IN_PROGRESS | --> | COMPLETED |
+----------+     +-------------+     +-----------+
                       |
                       | (if you quit early)
                       v
                 +-----------+
                 | ABANDONED |
                 +-----------+
```

### Spaced Repetition (SM-2 Algorithm)

The system schedules reviews at optimal intervals:

```
Day 1: Learn topic
Day 2: Review (short interval)
Day 4: Review (medium interval)
Day 8: Review (longer interval)
Day 16: Review (even longer)
...
Result: Long-term memory!
```

How it works:
- **Correct answer** → Interval increases (review less frequently)
- **Incorrect answer** → Interval resets to 1 day (review soon)
- **Ease factor** adjusts based on performance

### Feynman Technique Dialogues

The five phases of a Feynman dialogue:

1. **Opening** - AI asks you to explain the concept
2. **Probing** - AI asks "What do you mean by X?"
3. **Deepening** - AI asks edge cases and "what ifs"
4. **Testing** - AI asks for analogies and examples
5. **Closing** - AI evaluates your explanation

Why it works:
- Forces clear thinking (jargon doesn't work)
- Reveals gaps you didn't know existed
- Active learning is more effective than re-reading

### Learning Streaks

The system tracks daily consistency:
- Build streaks with daily sessions
- Warnings when streak is at risk
- Recovery plans after missed days

### Adaptive Difficulty

The system adjusts based on your performance:

| Quiz Score | System Response |
|------------|-----------------|
| ≥ 85% | "You've mastered this! Moving to harder topics" |
| 60-84% | "Good progress! A few more reviews should help" |
| < 60% | "Let's slow down and practice more" |

### Content Discovery

The Scout agent finds content from multiple sources:
- **arXiv**: Research papers by category (cs.AI, cs.LG, etc.)
- **YouTube**: Educational videos and tutorials
- **RSS**: Blog posts and newsletters
- **GitHub**: Code examples and repositories
- **Reddit**: Community discussions

Content is matched to your level using vector embeddings (semantic similarity).

---

## 10. How It Works - Technical Deep Dive

This section is for developers and curious learners who want to understand the internals.

### The Database

PostgreSQL stores all data in related tables:

**`users` table:**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Unique identifier |
| email | VARCHAR | User email |
| password_hash | VARCHAR | Bcrypt hash |
| is_active | BOOLEAN | Account status |
| created_at | TIMESTAMP | Registration date |

**`sessions` table:**
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Session identifier |
| user_id | UUID | Who is learning |
| planned_duration | INTEGER | Minutes planned |
| actual_duration | INTEGER | Minutes studied |
| status | VARCHAR | planned/in_progress/completed |

**`user_topic_progress` table:**
| Column | Type | Description |
|--------|------|-------------|
| user_id | UUID | User reference |
| topic | VARCHAR | Topic name |
| proficiency_level | FLOAT | 0.0 to 1.0 |
| next_review | TIMESTAMP | Spaced repetition date |
| ease_factor | FLOAT | SM-2 ease factor |

### Authentication Flow

1. **Registration**:
   - Validate email format and password strength
   - Hash password with bcrypt (slow, salted)
   - Store user record
   - Generate JWT tokens

2. **Login**:
   - Find user by email
   - Verify password against hash (constant-time)
   - Generate access token (24h) and refresh token (7d)
   - Return tokens to client

3. **Protected Requests**:
   - Client sends `Authorization: Bearer <token>`
   - Server validates JWT signature
   - Extract user_id from token payload
   - Process request

### JWT Token Structure

```
Access Token:
+------------------------------------------------+
| eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.          |
| eyJ1c2VyX2lkIjoiYWJjMTIzIiwiZXhwIjoxNzA1MzI5NjAwfQ. |
| SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c   |
+------------------------------------------------+
        |              |                |
     Header        Payload          Signature
   (algorithm)   (user_id, exp)   (proves validity)
```

### Vector Search

Content is stored with embeddings (1536-dimensional vectors):

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

Similar meanings produce similar vectors:
```
"attention mechanism" → [0.12, -0.45, 0.78, ..., 0.33]
"focus and weights"   → [0.11, -0.43, 0.79, ..., 0.32]  (similar!)
"cooking recipes"     → [-0.89, 0.12, -0.34, ..., 0.87] (different!)
```

### Security Features

**Rate Limiting**:
- Per-IP tracking with configurable limits
- Automatic cleanup prevents memory exhaustion
- Emergency cleanup when max records exceeded

**Password Security**:
- bcrypt with salt for hashing
- Constant-time comparison (prevents timing attacks)
- Strong validation requirements

**Audit Logging**:
- All auth events logged (login, register, password change)
- Email addresses masked in logs
- Sensitive data redacted

**CLI State Security**:
- Tokens stored with 0600 permissions (Unix)
- Atomic writes prevent corruption
- Secure location in user's config directory

### Key Design Patterns

**Repository Pattern**: Separates data access from business logic
```python
class QuizRepository:
    def get_by_user(self, user_id):
        return db.execute("SELECT * FROM quizzes WHERE user_id = ?", user_id)

class QuizService:
    def __init__(self, repository):
        self.repo = repository

    def get_average_score(self, user_id):
        quizzes = self.repo.get_by_user(user_id)
        return sum(q.score for q in quizzes) / len(quizzes)
```

**Dependency Injection**: Dependencies passed in, not created internally
```python
@app.post("/sessions")
def create_session(service: SessionService = Depends(get_session_service)):
    return service.create()
```

**Async/Await**: Non-blocking I/O for performance
```python
async def get_data():
    task1 = fetch_from_api_1()
    task2 = fetch_from_api_2()
    result1, result2 = await asyncio.gather(task1, task2)
    return result1, result2  # Parallel execution!
```

---

## 11. Deployment

### Docker Deployment

**Start the stack:**
```bash
# Build and start
docker-compose up -d

# Run migrations
docker-compose --profile tools run migrate

# View logs
docker-compose logs -f app

# Stop
docker-compose down
```

**Production Docker Compose** (`docker-compose.prod.yml`):
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - CORS_ORIGINS=${CORS_ORIGINS}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Production Checklist

Before deploying to production:

- [ ] Set `ENVIRONMENT=production`
- [ ] Generate strong `JWT_SECRET_KEY` (32+ chars)
- [ ] Configure `CORS_ORIGINS` with your frontend domain(s)
- [ ] Set up Redis for caching and rate limiting
- [ ] Enable HTTPS (required for HSTS)
- [ ] Configure proper logging
- [ ] Set up monitoring/alerting
- [ ] Rotate any exposed credentials
- [ ] Review database pool settings for your load

### Environment-Specific Settings

| Setting | Development | Production |
|---------|-------------|------------|
| `ENVIRONMENT` | `development` | `production` |
| `LOG_LEVEL` | `DEBUG` | `INFO` |
| `CORS_ORIGINS` | (defaults to localhost) | Your frontend domain(s) |
| HSTS | Disabled | Enabled |
| Error details | Shown | Hidden |

---

## 12. Troubleshooting

### Database Connection Error

```
Error: Connection refused
```

**Solutions:**
1. Verify `DATABASE_URL` includes `+asyncpg` after `postgresql`
2. Verify URL ends with `?sslmode=require`
3. Check Neon dashboard for connection limits
4. Try regenerating connection string in Neon

### Authentication Failed

```
Error: Invalid or expired token
```

**Solutions:**
1. Re-login: `learner auth login`
2. Check `JWT_SECRET_KEY` is set in `.env`
3. Verify token hasn't expired (24h default)
4. Try refreshing token: `learner auth refresh`

### API Key Error

```
Error: Invalid API key
```

**Solutions:**
1. Verify `ANTHROPIC_API_KEY` in `.env`
2. Check for extra spaces or quotes in the value
3. Verify key is active at console.anthropic.com
4. Check API usage limits

### Redis Connection Warning

```
Warning: Redis not available
```

**Solutions:**
1. This is optional for development - can be ignored
2. For production: set up Redis/Upstash and add `REDIS_URL` to `.env`
3. Verify Redis URL format (use `rediss://` for TLS)

### Rate Limit Exceeded

```
Error: Too many requests (HTTP 429)
```

**Solutions:**
1. Wait for the `Retry-After` period
2. Check if you're hitting login repeatedly (5/5min limit)
3. Registration is limited to 3/hour

### Password Validation Failed

```
Error: Password must contain at least one special character
```

**Requirements:**
- 8-128 characters
- At least one uppercase (A-Z)
- At least one lowercase (a-z)
- At least one digit (0-9)
- At least one special character (!@#$%^&*(),.?":{}|<>-_=+[]\\;'`~)
- Not a common password

### Import/Module Errors

```
ModuleNotFoundError: No module named 'xxx'
```

**Solutions:**
1. Install dependencies: `pip install -r requirements.txt`
2. Activate virtual environment if using one
3. Verify Python version is 3.11+

### CLI State Corruption

```
Error: JSON decode error in state file
```

**Solutions:**
1. Clear CLI state: delete `~/.config/learner/state.json` (Linux/macOS) or `%APPDATA%\learner\state.json` (Windows)
2. Re-login: `learner auth login`

---

## 13. Quick Reference

### CLI Command Cheat Sheet

```bash
# Authentication
learner auth register          # Create account
learner auth login             # Sign in
learner auth logout            # Sign out
learner auth whoami            # Current user
learner auth change-password   # Change password

# Learning Sessions
learner start                  # Start session (30 min default)
learner start --time 45        # Custom duration
learner start --type drill     # Practice mode
learner status                 # Current session info
learner learn end              # End session

# Assessment
learner quiz                   # Take a quiz
learner quiz --topic "X"       # Quiz on topic
learner explain "X"            # Feynman dialogue

# Progress
learner stats summary          # Overview
learner stats streak           # Current streak
learner stats topics           # Topic mastery

# Profile
learner profile onboarding     # Setup wizard
learner profile show           # View profile
```

### Key API Endpoints

```
POST /auth/register            # Create account
POST /auth/login               # Get tokens
POST /sessions                 # Start session
GET  /sessions/current         # Active session
POST /assessments/quiz         # Generate quiz
POST /assessments/feynman      # Start Feynman
GET  /content/feed             # Get content
```

### Environment Variables Quick Reference

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql+asyncpg://...
JWT_SECRET_KEY=...

# Production Required
CORS_ORIGINS=https://myapp.com

# Optional
REDIS_URL=rediss://...
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### Database Tables

| Table | Purpose |
|-------|---------|
| `users` | Account information |
| `user_profiles` | Learning preferences |
| `sessions` | Learning session records |
| `session_activities` | Activities within sessions |
| `quizzes` | Quiz records and results |
| `quiz_questions` | Individual questions |
| `content` | Learning materials |
| `user_topic_progress` | Proficiency tracking |
| `learning_patterns` | Streak and behavior data |

### Files to Study (Developers)

| File | Purpose |
|------|---------|
| `migrations/001_initial_schema.sql` | Database structure |
| `src/shared/config.py` | Configuration |
| `src/modules/auth/service.py` | Authentication logic |
| `src/modules/agents/orchestrator.py` | Agent coordination |
| `src/modules/session/service.py` | Session management |
| `src/cli/main.py` | CLI entry point |
| `src/api/main.py` | API entry point |

---

## Summary

Learner is a comprehensive platform for mastering AI/ML concepts through:

- **Structured learning sessions** with balanced consumption and production
- **6 specialized AI agents** that work together seamlessly
- **Adaptive assessments** that adjust to your level
- **Feynman dialogues** that expose knowledge gaps
- **Spaced repetition** for long-term retention
- **Multi-source content** curation

Get started in minutes:
1. Clone the repository
2. Set up Neon PostgreSQL
3. Configure `.env` with required keys
4. Run migrations
5. Start learning!

---

