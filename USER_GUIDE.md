# AI Learning System - User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Who Should Use This Application](#who-should-use-this-application)
3. [Installation Requirements](#installation-requirements)
4. [Quick Start Guide](#quick-start-guide)
5. [Using the CLI](#using-the-cli)
6. [Using the API](#using-the-api)
7. [Key Features](#key-features)
8. [Agent System](#agent-system)
9. [Troubleshooting](#troubleshooting)

---

## Introduction

### What is the AI Learning System?

The **AI Learning System** is a hyper-personalized learning platform designed to help users master AI and machine learning concepts through evidence-based learning techniques. It combines principles from:

- **Ultralearning** (Scott Young) - Focus, directness, and retrieval practice
- **Learning How to Learn** (Barbara Oakley) - Chunking, spaced repetition, and focused/diffuse thinking
- **Feynman Technique** - Teaching concepts in simple terms to identify knowledge gaps

### Problems It Solves

| Traditional Learning Problem | How This System Solves It |
|------------------------------|---------------------------|
| Passive consumption (watching tutorials) | Enforces 50/50 balance between consumption and production |
| Illusion of competence | AI "confused student" dialogues expose knowledge gaps |
| Information overload | Aggregates and curates content from multiple sources |
| One-size-fits-all pacing | Adapts difficulty and pace based on performance |
| Poor retention | Implements spaced repetition for long-term memory |

---

## Who Should Use This Application

### Target Audience

| User Type | Use Case |
|-----------|----------|
| **AI/ML Learners** | Learning artificial intelligence, machine learning, or data science |
| **Self-directed Learners** | Prefer structured self-study over traditional courses |
| **Professionals Upskilling** | Software engineers or data analysts expanding into AI/ML |
| **Students** | Computer science students supplementing academic learning |
| **Interview Preparation** | Systematic study of ML concepts with assessment |
| **Researchers** | Breaking down arXiv papers with Feynman dialogues |

### Ideal Use Cases

1. **Daily Learning Practice**: 30-60 minute focused sessions on AI topics
2. **Interview Preparation**: Systematic study with quizzes and assessments
3. **Research Paper Understanding**: Deep dive into papers with Feynman technique
4. **Skill Gap Identification**: Finding weak areas through targeted practice
5. **Long-term Knowledge Retention**: Spaced repetition prevents forgetting

---

## Installation Requirements

### System Requirements

| Requirement | Specification |
|-------------|---------------|
| **Python** | 3.11 or higher |
| **Operating System** | Windows, macOS, or Linux |
| **Memory** | 4GB RAM minimum |
| **Storage** | 500MB for application |

### Database Requirements

| Service | Provider | Free Tier |
|---------|----------|-----------|
| **PostgreSQL** | [Neon.tech](https://neon.tech) (Recommended) | 512MB storage |
| **Redis** | [Upstash](https://upstash.com) (Optional) | 10K requests/day |

### Required API Keys

| API Key | Provider | Purpose | Required? |
|---------|----------|---------|-----------|
| `ANTHROPIC_API_KEY` | [Anthropic Console](https://console.anthropic.com/) | Claude AI for agents | **Yes** |
| `DATABASE_URL` | [Neon.tech](https://neon.tech) | PostgreSQL database | **Yes** |
| `JWT_SECRET_KEY` | Self-generated | Authentication tokens | **Yes** |

### Optional API Keys

| API Key | Provider | Purpose |
|---------|----------|---------|
| `OPENAI_API_KEY` | [OpenAI Platform](https://platform.openai.com/) | Text embeddings |
| `REDIS_URL` | [Upstash](https://upstash.com) | Caching/rate limiting |
| `YOUTUBE_API_KEY` | Google Cloud | Content ingestion |
| `GITHUB_TOKEN` | GitHub Settings | Content ingestion |

### Python Dependencies

Core dependencies (installed automatically):

```
fastapi, uvicorn          # API Framework
typer, rich               # CLI Interface
sqlalchemy, asyncpg       # Database
anthropic                 # AI Integration
pyjwt, bcrypt, passlib    # Authentication
pydantic, pydantic-settings # Validation
httpx                     # HTTP Client
feedparser, arxiv         # Content Processing
```

---

## Quick Start Guide

### Step 1: Clone and Install

```bash
# Clone repository
git clone <repository-url>
cd Learner

# Install dependencies using pip
pip install -r requirements.txt

# Or using Poetry
poetry install
```

### Step 2: Set Up Database (Neon PostgreSQL)

1. **Create a Neon Account**
   - Go to [neon.tech](https://neon.tech)
   - Sign up for free (512MB included)

2. **Create a Project**
   - Click "New Project"
   - Name: `ai-learning-system`
   - Choose your region
   - Click "Create Project"

3. **Get Connection String**
   - Go to Dashboard → Connection Details
   - Copy the connection string
   - **Important**: Add `+asyncpg` after `postgresql` and `?sslmode=require` at the end

   Example:
   ```
   postgresql+asyncpg://user:password@ep-xxx.region.aws.neon.tech/neondb?sslmode=require
   ```

### Step 3: Configure Environment

```bash
# Create environment file
cp .env.example .env

# Edit with your credentials
# On Windows: notepad .env
# On macOS/Linux: nano .env
```

**Required environment variables:**

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
JWT_SECRET_KEY=your-secret-key-here

# Generate JWT secret (PowerShell)
# [System.Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))

# Generate JWT secret (Linux/macOS)
# openssl rand -hex 32
```

### Step 4: Run Database Migrations

```bash
python migrate.py
```

Expected output:
```
==================================================
AI Learning System - Database Migration
==================================================

Connecting to: postgresql+asyncpg://user:pass@...
Found 76 SQL statements to execute

  [1/76] ✓ CREATE EXTENSION IF NOT EXISTS "uuid-ossp"...
  ...
  [76/76] ✓ Done

✓ All statements executed successfully!
Found 15 tables.
```

### Step 5: Start Using the Application

**CLI Mode:**
```bash
python -m src.cli.main --help
```

**API Mode:**
```bash
uvicorn src.api.main:app --reload --port 8000
```

---

## Using the CLI

### Authentication Commands

```bash
# Register a new account
python -m src.cli.main auth register

# Login
python -m src.cli.main auth login

# Check current user
python -m src.cli.main auth whoami

# Logout
python -m src.cli.main auth logout
```

### Learning Session Commands

```bash
# Start a learning session
python -m src.cli.main start
python -m src.cli.main start --time 45          # 45 minutes
python -m src.cli.main start --type drill       # Focused practice

# Check session status
python -m src.cli.main status

# End session
python -m src.cli.main learn end
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
python -m src.cli.main quiz
python -m src.cli.main quiz --topic "transformers" --count 5

# Feynman dialogue (explain a topic)
python -m src.cli.main explain "attention mechanisms"
```

### Progress Commands

```bash
# View statistics
python -m src.cli.main stats summary

# View streak
python -m src.cli.main stats streak

# View topic mastery
python -m src.cli.main stats topics
```

### Profile Commands

```bash
# Complete onboarding
python -m src.cli.main profile onboarding

# Update preferences
python -m src.cli.main profile update

# View profile
python -m src.cli.main profile show
```

---

## Using the API

### Starting the API Server

```bash
# Development mode
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### API Documentation

Once running, access documentation at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Available Endpoints

#### Authentication (`/auth`)
```
POST /auth/register          - Create new account
POST /auth/login             - Get access tokens
POST /auth/refresh           - Refresh access token
POST /auth/logout            - Logout
POST /auth/change-password   - Change password
```

#### Sessions (`/sessions`)
```
POST /sessions               - Start new session
GET /sessions/current        - Get active session
GET /sessions/{id}           - Get session details
DELETE /sessions/{id}        - End session
GET /sessions/history        - Get session history
GET /sessions/streak         - Get learning streak
```

#### Assessments (`/assessments`)
```
POST /assessments/quiz       - Generate quiz
POST /assessments/quiz/{id}/submit   - Submit answers
POST /assessments/feynman    - Start Feynman dialogue
POST /assessments/feynman/{id}/message   - Continue dialogue
GET /assessments/reviews     - Get due reviews
```

#### Content (`/content`)
```
GET /content                 - List content
POST /content/search         - Search content
GET /content/recommendations - Get personalized recommendations
```

### Example API Usage

**Register:**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123"
  }'
```

**Start Session:**
```bash
curl -X POST http://localhost:8000/sessions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "available_minutes": 45,
    "session_type": "regular"
  }'
```

---

## Key Features

### 1. Adaptive Learning Sessions

The system creates personalized session plans with a 50/50 balance:

| Phase | Time | Activities |
|-------|------|------------|
| **Consumption** | 50% | Reading articles, watching videos |
| **Production** | 50% | Quizzes, Feynman dialogues, coding |

### 2. Spaced Repetition

Uses the SM-2 algorithm to schedule reviews:
- **Correct answers** → Interval increases (review less frequently)
- **Incorrect answers** → Interval resets (review soon)
- Topics automatically scheduled for optimal retention

### 3. Feynman Technique Dialogues

AI "confused student" helps you explain topics:
1. You explain a concept
2. AI asks probing questions
3. You refine your explanation
4. AI identifies gaps in understanding
5. Final evaluation with scores

### 4. Adaptive Difficulty

System adjusts based on performance:
- **High quiz scores** → Faster pace, harder questions
- **Low quiz scores** → Slower pace, more review
- **Struggling topics** → Additional practice exercises

### 5. Multi-Source Content

Aggregates content from:
- arXiv (research papers)
- YouTube (educational videos)
- RSS feeds (blogs, newsletters)
- GitHub (code examples)
- Reddit (community discussions)

### 6. Learning Streaks

Tracks daily learning consistency:
- Build streaks with daily sessions
- Warnings when streak is at risk
- Recovery plans after missed days

---

## Agent System

The application uses specialized AI agents for different tasks:

### Available Agents

| Agent | Role | When Used |
|-------|------|-----------|
| **Coach** | Motivation & session management | Session start/end, encouragement |
| **Socratic** | Feynman dialogues ("confused student") | When explaining topics |
| **Assessment** | Quiz generation & evaluation | During quizzes |
| **Curriculum** | Learning path planning | Topic recommendations |
| **Scout** | Content discovery | Finding relevant articles/videos |
| **Drill Sergeant** | Targeted practice | Skill building exercises |

### How Agents Work Together

```
User: "I want to learn transformers"
  → Curriculum Agent: Creates learning path

User: "Start session"
  → Coach Agent: "Let's begin! Here's your 45-minute plan..."

User: "Quiz me"
  → Assessment Agent: Generates adaptive questions

User: "Let me explain attention"
  → Socratic Agent: "I'm confused, help me understand..."

User: "Done for today"
  → Coach Agent: "Great session! You covered X topics..."
```

---

## Troubleshooting

### Common Issues

#### Database Connection Error
```
Error: Connection refused
```
**Solution:** Verify `DATABASE_URL` in `.env` includes:
- `+asyncpg` after `postgresql`
- `?sslmode=require` at the end

#### Authentication Failed
```
Error: Invalid or expired token
```
**Solution:**
- Re-login with `python -m src.cli.main auth login`
- Check `JWT_SECRET_KEY` is set in `.env`

#### API Key Error
```
Error: Invalid API key
```
**Solution:**
- Verify `ANTHROPIC_API_KEY` in `.env`
- Check for extra spaces or quotes

#### Redis Connection (Optional)
```
Warning: Redis not available
```
**Solution:** This is optional for development. For production:
- Set up Redis or use Upstash
- Add `REDIS_URL` to `.env`

### Getting Help

1. Check the [README.md](README.md) for additional information
2. Review [DESIGN_IMPROVEMENTS_REPORT.md](DESIGN_IMPROVEMENTS_REPORT.md) for architecture details
3. Check API documentation at `/docs` when server is running

---

## Docker Deployment (Optional)

```bash
# Start full stack
docker-compose up -d

# Run migrations
docker-compose --profile tools run migrate

# View logs
docker-compose logs -f app

# Stop
docker-compose down
```

---

## Summary

The AI Learning System is a comprehensive platform for mastering AI/ML concepts through:

- **Structured learning sessions** with balanced consumption and production
- **AI-powered assessments** that adapt to your level
- **Feynman dialogues** that expose knowledge gaps
- **Spaced repetition** for long-term retention
- **Multi-source content** curation

Get started in minutes with the Quick Start Guide above!
