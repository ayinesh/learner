# How This Learning App Works

## A Beginner-Friendly Guide for First-Year Computer Science Students

---

## Table of Contents

1. [What Is This App?](#1-what-is-this-app)
2. [The Big Picture](#2-the-big-picture)
3. [How the Code Is Organized](#3-how-the-code-is-organized)
4. [The Database - Where Data Lives](#4-the-database---where-data-lives)
5. [The API - How Programs Talk to Each Other](#5-the-api---how-programs-talk-to-each-other)
6. [The CLI - Typing Commands in the Terminal](#6-the-cli---typing-commands-in-the-terminal)
7. [The AI Agents - The Smart Helpers](#7-the-ai-agents---the-smart-helpers)
8. [How Users Log In - Authentication](#8-how-users-log-in---authentication)
9. [Learning Sessions - The Main Feature](#9-learning-sessions---the-main-feature)
10. [Quizzes and Assessments](#10-quizzes-and-assessments)
11. [The Feynman Technique - Learn by Teaching](#11-the-feynman-technique---learn-by-teaching)
12. [Content and Vector Search](#12-content-and-vector-search)
13. [A Complete Journey Through the App](#13-a-complete-journey-through-the-app)
14. [Key Programming Concepts Used](#14-key-programming-concepts-used)
15. [Files to Study If You Want to Learn More](#15-files-to-study-if-you-want-to-learn-more)

---

## 1. What Is This App?

This is a **personalized learning system** that helps you learn topics (especially AI and machine learning) in a smart way. Think of it as having a personal tutor that:

- Creates a custom study plan for you
- Finds articles, videos, and papers that match your level
- Quizzes you to check if you really understand
- Makes you explain concepts in simple words (to find gaps in your knowledge)
- Remembers what you know and what you need to review
- Motivates you with streaks and progress tracking

### Why Is It "Smart"?

Unlike a regular learning website, this app uses **6 AI assistants** (we call them "agents") that work together to help you. Each agent specializes in something different:

| Agent | Job |
|-------|-----|
| Coach | Motivates you, opens/closes sessions |
| Curriculum | Plans what you should learn next |
| Scout | Finds relevant content for you |
| Assessment | Creates quizzes to test you |
| Socratic | Plays a "confused student" so you can teach (Feynman technique) |
| Drill Sergeant | Makes you practice your weak areas |

---

## 2. The Big Picture

Here's how the whole system fits together:

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER                                     │
│                           │                                      │
│              ┌────────────┴────────────┐                        │
│              ▼                         ▼                        │
│        ┌─────────┐              ┌─────────────┐                 │
│        │   CLI   │              │  REST API   │                 │
│        │(Terminal)│              │ (Web/Apps)  │                 │
│        └────┬────┘              └──────┬──────┘                 │
│             │                          │                        │
│             └──────────┬───────────────┘                        │
│                        ▼                                        │
│            ┌──────────────────────┐                             │
│            │   BUSINESS LOGIC     │                             │
│            │                      │                             │
│            │  ┌────────────────┐  │                             │
│            │  │ AUTH MODULE    │  │  (handles login)            │
│            │  ├────────────────┤  │                             │
│            │  │ SESSION MODULE │  │  (manages learning time)    │
│            │  ├────────────────┤  │                             │
│            │  │ CONTENT MODULE │  │  (finds study materials)    │
│            │  ├────────────────┤  │                             │
│            │  │ ASSESSMENT     │  │  (creates quizzes)          │
│            │  ├────────────────┤  │                             │
│            │  │ AGENTS MODULE  │  │  (6 AI helpers)             │
│            │  └────────────────┘  │                             │
│            └───────────┬──────────┘                             │
│                        ▼                                        │
│            ┌──────────────────────┐                             │
│            │      DATABASE        │                             │
│            │    (PostgreSQL)      │                             │
│            │                      │                             │
│            │  Users, Sessions,    │                             │
│            │  Quizzes, Content,   │                             │
│            │  Progress, etc.      │                             │
│            └──────────────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
```

**What's happening here?**

1. **USER** - That's you! You interact with the app.
2. **CLI/API** - Two ways to talk to the app (terminal commands or web requests).
3. **Business Logic** - The code that does the actual work.
4. **Database** - Where all your data is stored permanently.

---

## 3. How the Code Is Organized

The code follows a pattern called **modular architecture**. This means different features are separated into different folders. Here's what each folder does:

```
src/
├── api/                    # REST API (for web/mobile apps)
│   ├── main.py            # Starts the API server
│   ├── routers/           # Defines all URL endpoints
│   │   ├── auth.py        # Login/logout endpoints
│   │   ├── sessions.py    # Learning session endpoints
│   │   ├── content.py     # Content search endpoints
│   │   └── assessments.py # Quiz endpoints
│   ├── middleware/        # Security checks for requests
│   └── schemas/           # Data validation rules
│
├── cli/                    # Terminal Interface
│   ├── main.py            # Main command definitions
│   ├── nlp_parser.py      # Understands natural language ("quiz me")
│   ├── state.py           # Remembers if you're logged in
│   ├── commands/          # Different command groups
│   └── ui/                # Pretty terminal output
│
├── modules/                # The Brain of the App
│   ├── auth/              # Login/password handling
│   ├── user/              # User profiles and preferences
│   ├── session/           # Learning sessions
│   ├── content/           # Study materials
│   ├── assessment/        # Quizzes and tests
│   ├── adaptation/        # Personalizes difficulty
│   ├── agents/            # 6 AI helpers
│   └── llm/               # Talks to Claude AI
│
└── shared/                 # Code used everywhere
    ├── config.py          # Settings (database URL, etc.)
    ├── database.py        # Database connection
    └── exceptions.py      # Error definitions
```

### Why Organize Code This Way?

1. **Easier to understand** - Each folder has one job
2. **Easier to fix bugs** - You know exactly where to look
3. **Easier for teams** - Different people can work on different parts
4. **Easier to test** - You can test each module separately

---

## 4. The Database - Where Data Lives

A **database** is like a giant organized spreadsheet that stores all your data permanently. We use **PostgreSQL**, which is a popular database.

### The Main Tables (Like Spreadsheets)

Think of each table as an Excel sheet with rows and columns:

#### `users` - Stores Account Information
| Column | What It Stores | Example |
|--------|---------------|---------|
| id | Unique identifier | `abc123-def456` |
| email | Your email | `student@university.edu` |
| password_hash | Encrypted password | `$2b$12$xyz...` |
| status | Account status | `active` |
| created_at | When you signed up | `2024-01-15` |

#### `sessions` - Learning Sessions
| Column | What It Stores | Example |
|--------|---------------|---------|
| id | Unique session ID | `sess-789` |
| user_id | Who is learning | `abc123` |
| planned_duration | How long you planned | `30` minutes |
| actual_duration | How long you actually studied | `32` minutes |
| status | Session state | `completed` |

#### `user_topic_progress` - What You Know
| Column | What It Stores | Example |
|--------|---------------|---------|
| user_id | Who | `abc123` |
| topic | What subject | `attention-mechanism` |
| proficiency_level | How well you know it (0-1) | `0.75` |
| next_review | When to study again | `2024-01-18` |
| ease_factor | How easy it is for you | `2.5` |

#### `quizzes` - Quiz Records
| Column | What It Stores | Example |
|--------|---------------|---------|
| id | Quiz ID | `quiz-456` |
| user_id | Who took it | `abc123` |
| questions | The quiz questions | `[{...}, {...}]` |
| score | Your result | `4/5` |

### How Tables Connect (Relationships)

Tables are linked together. For example:
- A **user** can have many **sessions**
- A **session** can have many **activities**
- A **quiz** belongs to one **user**

```
users (1) ──────< sessions (many)
   │
   └──────────────< quizzes (many)
```

The database file is: `migrations/001_initial_schema.sql`

---

## 5. The API - How Programs Talk to Each Other

An **API** (Application Programming Interface) lets different programs communicate. Think of it as a waiter in a restaurant:

```
You (Customer)  ──  "I want pizza"  ──►  Waiter (API)  ──►  Kitchen (Server)

You (Customer)  ◄──  [Pizza!]  ◄──────  Waiter (API)  ◄──  Kitchen (Server)
```

### HTTP Methods (Types of Requests)

| Method | What It Does | Example |
|--------|-------------|---------|
| GET | Fetch data | "Show me my progress" |
| POST | Create something | "Start a new session" |
| PUT | Update something | "Change my profile" |
| DELETE | Remove something | "Cancel this session" |

### Our Main API Endpoints

An **endpoint** is a URL that does something specific:

#### Authentication (`/auth`)
```
POST /auth/register     → Create new account
POST /auth/login        → Sign in
POST /auth/logout       → Sign out
POST /auth/refresh      → Get new access token
GET  /auth/me          → Get your info
```

#### Sessions (`/sessions`)
```
POST /sessions          → Start learning session
GET  /sessions/active   → Get current session
PUT  /sessions/{id}/end → End session
GET  /sessions/history  → See past sessions
```

#### Assessments (`/assessments`)
```
POST /assessments/quiz/generate     → Make a quiz
POST /assessments/quiz/{id}/submit  → Submit answers
POST /assessments/feynman/start     → Start Feynman dialogue
```

### Example API Call

```
Request:
POST /auth/login
Body: {
    "email": "student@uni.edu",
    "password": "mypassword123"
}

Response:
{
    "access_token": "eyJhbGciOiJIUzI1...",
    "refresh_token": "eyJhbGciOiJIUzI1...",
    "user": {
        "id": "abc123",
        "email": "student@uni.edu"
    }
}
```

The API code is in: `src/api/`

---

## 6. The CLI - Typing Commands in the Terminal

The **CLI** (Command Line Interface) lets you use the app by typing commands in the terminal. It's like texting the app instead of clicking buttons.

### Basic Commands

```bash
# Sign up
learner auth register

# Start studying
learner start --time 30

# Take a quiz
learner quiz --topic "Python"

# Check your stats
learner stats progress

# Natural language also works!
learner chat "quiz me on attention"
```

### How the CLI Works

```
┌──────────────────────────────────────────────────────────────┐
│  You type: learner start --time 30                           │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  main.py parses command                               │   │
│  │  - Checks if you're logged in                         │   │
│  │  - Validates the time value                           │   │
│  └───────────────────────┬──────────────────────────────┘   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Session Service                                      │   │
│  │  - Creates new session in database                    │   │
│  │  - Asks AI agents to plan your session                │   │
│  └───────────────────────┬──────────────────────────────┘   │
│                          ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Coach Agent                                          │   │
│  │  - Generates welcome message                          │   │
│  │  - "Welcome back! 3-day streak! Let's learn..."       │   │
│  └───────────────────────┬──────────────────────────────┘   │
│                          ▼                                   │
│  Output displayed in your terminal                           │
└──────────────────────────────────────────────────────────────┘
```

### Natural Language Parser

The app can understand plain English! When you type:

```bash
learner chat "quiz me on transformers for 10 minutes"
```

The **NLP Parser** (`nlp_parser.py`) does this:

1. **Sanitize** - Blocks dangerous inputs (like SQL injection)
2. **Classify** - Uses AI to understand your intent
3. **Extract** - Pulls out details (topic: "transformers", time: 10)
4. **Execute** - Runs the right command

The CLI code is in: `src/cli/`

---

## 7. The AI Agents - The Smart Helpers

This is the coolest part! The app uses **6 specialized AI agents** that work together, powered by Claude AI.

### The Orchestrator - The Traffic Controller

Before we talk about agents, meet the **Orchestrator** (`orchestrator.py`). It decides which agent should handle your request.

```
You: "Start a session"
         │
         ▼
   ┌───────────┐
   │ORCHESTRATOR│ ── "This is a session start... Coach should handle this"
   └─────┬─────┘
         │
         ▼
   ┌───────────┐
   │   COACH   │ ── "Welcome back! Let's plan your session..."
   └───────────┘
```

### Agent 1: Coach Agent (`coach.py`)

**Job**: Motivation and session management

**What it does**:
- Opens sessions with personalized greetings
- Tracks your learning streak
- Closes sessions with summaries
- Helps when you've been away

**Example output**:
```
"Welcome back! You're on a 5-day streak!
Today we'll continue with attention mechanisms.
Your last quiz score was 80% - great progress!"
```

### Agent 2: Curriculum Agent (`curriculum.py`)

**Job**: Plans what you should learn

**What it does**:
- Creates a learning roadmap (like a syllabus)
- Recommends what topic to study next
- Considers your goals and available time
- Balances new topics with review

**Example output**:
```
Week 1: Attention Basics
  - Day 1-2: What is attention?
  - Day 3-4: Query-Key-Value mechanics

Week 2: Transformer Architecture
  - Day 1-2: Encoder structure
  - Day 3-4: Decoder structure
```

### Agent 3: Scout Agent (`scout.py`)

**Job**: Finds learning content

**What it does**:
- Searches for relevant articles, videos, papers
- Matches content to your skill level
- Filters based on your preferences
- Summarizes what each content is about

### Agent 4: Assessment Agent (`assessment_agent.py`)

**Job**: Creates and grades quizzes

**What it does**:
- Generates questions based on what you learned
- Adjusts difficulty (starts easy, gets harder)
- Identifies your knowledge gaps
- Uses **spaced repetition** (more on this later)

**Question types**:
- Multiple choice
- Short answer
- Scenarios ("What would happen if...")
- Comparisons ("How is X different from Y?")

### Agent 5: Socratic Agent (`socratic.py`)

**Job**: The "confused student" for Feynman technique

**What it does**:
- Pretends to be a smart but uninformed student
- Asks you to explain concepts simply
- Challenges vague explanations
- Exposes gaps in your understanding

**Example dialogue**:
```
You: "Attention helps the model focus on relevant parts."
AI: "Wait, I'm confused. How does a computer 'focus'?
    Does it have eyes?"
You: "Well, it assigns weights to different inputs..."
AI: "Weights? Like gym weights? What determines these weights?"
```

### Agent 6: Drill Sergeant Agent (`drill_sergeant.py`)

**Job**: Targeted practice on weak areas

**What it does**:
- Identifies skills you struggle with
- Creates focused exercises
- Pushes you to improve weak points
- Tracks your improvement

### How Agents Work Together

Here's a typical session showing agent collaboration:

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

The agents code is in: `src/modules/agents/`

---

## 8. How Users Log In - Authentication

**Authentication** means verifying "you are who you say you are." Here's how it works:

### Step 1: Registration

```
You provide:
  - Email: student@uni.edu
  - Password: supersecret123

The system:
  1. Checks if email exists (can't have duplicates)
  2. Hashes the password (turns it into random-looking text)
  3. Stores: email + hashed_password
```

### Why Hash Passwords?

We never store your actual password! Instead, we use **bcrypt** to create a "hash":

```
Your password: "supersecret123"
                    │
                    ▼ (bcrypt hashing)

Stored hash: "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4beW...."
```

The hash is:
- **One-way** - You can't reverse it to get the password
- **Unique** - Same password = different hash each time (due to "salt")
- **Slow** - Takes time to compute (prevents hackers from guessing quickly)

### Step 2: Login

```
You provide: email + password

The system:
  1. Finds user by email
  2. Hashes the password you typed
  3. Compares with stored hash
  4. If match → generates JWT tokens
```

### What Are JWT Tokens?

**JWT** (JSON Web Token) is like a digital ID card:

```
Access Token (short-lived, 24 hours):
┌─────────────────────────────────────────────────────┐
│ eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.               │
│ eyJ1c2VyX2lkIjoiYWJjMTIzIiwiZXhwIjoxNzA1MzI5NjAwfQ. │
│ SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c         │
└─────────────────────────────────────────────────────┘
        │              │                │
     Header        Payload          Signature
   (algorithm)   (your user_id)   (proves it's real)
```

**Refresh Token** (longer-lived, 7 days):
- Used to get a new access token when the old one expires
- Stored securely in the database

### The Login Flow

```
┌────────────────────────────────────────────────────────────────┐
│                       LOGIN FLOW                                │
│                                                                 │
│  1. You type username/password                                  │
│                    │                                            │
│                    ▼                                            │
│  2. Server checks credentials                                   │
│                    │                                            │
│         ┌─────────┴─────────┐                                  │
│         │                   │                                   │
│         ▼                   ▼                                   │
│     INVALID              VALID                                  │
│    "Wrong password"        │                                    │
│                           │                                    │
│                           ▼                                    │
│              3. Generate tokens                                 │
│                    │                                            │
│                    ▼                                            │
│              4. Return tokens                                   │
│                    │                                            │
│                    ▼                                            │
│              5. CLI saves tokens locally                        │
│                 (state.json file)                               │
│                    │                                            │
│                    ▼                                            │
│              6. Future requests include                         │
│                 "Authorization: Bearer <token>"                 │
└────────────────────────────────────────────────────────────────┘
```

The auth code is in: `src/modules/auth/`

---

## 9. Learning Sessions - The Main Feature

A **learning session** is a focused study period with planned activities.

### Session Lifecycle

```
┌──────────┐     ┌─────────────┐     ┌───────────┐
│ PLANNED  │ ──► │ IN_PROGRESS │ ──► │ COMPLETED │
└──────────┘     └─────────────┘     └───────────┘
                        │
                        │ (if you quit early)
                        ▼
                 ┌───────────┐
                 │ ABANDONED │
                 └───────────┘
```

### What Happens When You Start a Session

```python
# You run: learner start --time 30

# Step 1: Create session record
session = {
    "user_id": your_id,
    "planned_duration": 30,
    "status": "in_progress",
    "started_at": now
}

# Step 2: Get your context
context = {
    "proficiency_levels": {...},     # What you know
    "knowledge_gaps": [...],         # What you don't know
    "items_due_for_review": [...],   # Spaced repetition
    "streak": 5                      # Days in a row
}

# Step 3: Generate session plan (50% reading, 50% practice)
plan = [
    {"type": "content_read", "duration": 15, "topic": "attention"},
    {"type": "quiz", "duration": 10, "questions": 5},
    {"type": "feynman", "duration": 5, "topic": "attention"}
]

# Step 4: Coach generates welcome message
message = "Welcome back! 5-day streak! Today: attention mechanisms."
```

### Session Activities

During a session, you do various activities:

| Activity Type | What It Is | Duration |
|--------------|-----------|----------|
| `content_read` | Reading an article/watching video | 10-20 min |
| `quiz` | Answering questions | 5-15 min |
| `feynman` | Explaining to the AI "student" | 5-10 min |
| `practice` | Targeted exercises on weak areas | 5-15 min |

Each activity is recorded:
```sql
INSERT INTO session_activities (
    session_id,
    activity_type,
    started_at,
    completed_at,
    performance_data
);
```

### When the Session Ends

```python
# You run: learner session end

# Step 1: Calculate stats
stats = {
    "actual_duration": 32,  # minutes
    "activities_completed": 3,
    "quiz_score": 0.8,      # 80%
    "topics_covered": ["attention"]
}

# Step 2: Update learning patterns
update_streak(user_id)           # 5 → 6 days
update_proficiency(user_id)       # attention: 0.5 → 0.7
schedule_reviews(user_id)         # Next review in 2 days

# Step 3: Coach generates summary
summary = """
Great session!
- Studied for 32 minutes
- Quiz score: 80%
- Attention mechanism proficiency: 70%
- 6-day streak!
- Next: review attention in 2 days, then transformers
"""
```

The session code is in: `src/modules/session/`

---

## 10. Quizzes and Assessments

The assessment system tests your knowledge and tracks your progress.

### How Quizzes Are Generated

```
┌────────────────────────────────────────────────────────────────┐
│                    QUIZ GENERATION                              │
│                                                                 │
│  Input:                                                         │
│    - Topic: "attention mechanism"                               │
│    - Your proficiency: 0.6 (60%)                               │
│    - Number of questions: 5                                     │
│                                                                 │
│                          │                                      │
│                          ▼                                      │
│                                                                 │
│  Claude AI generates questions based on:                        │
│    - Your current skill level (not too easy, not too hard)     │
│    - Content you've read                                        │
│    - Questions you've missed before                             │
│                                                                 │
│                          │                                      │
│                          ▼                                      │
│                                                                 │
│  Questions:                                                     │
│  1. [Multiple Choice] What does attention compute?              │
│     A) A weighted sum of values                                 │
│     B) The maximum value                                        │
│     C) A random sample                                          │
│                                                                 │
│  2. [Short Answer] Explain query-key-value in one sentence      │
│                                                                 │
│  3. [Scenario] If attention weights are all equal...            │
│                                                                 │
│  4. [Comparison] Difference between self-attention and...       │
│                                                                 │
│  5. [Application] How would you modify attention for...         │
└────────────────────────────────────────────────────────────────┘
```

### Spaced Repetition - The Secret to Remembering

**Spaced repetition** is a learning technique where you review information at increasing intervals. The idea: review just before you forget!

```
Normal studying:
Day 1: Learn → Day 2: Forget 😢

Spaced repetition:
Day 1: Learn
Day 2: Review (short interval)
Day 4: Review (medium interval)
Day 8: Review (longer interval)
Day 16: Review (even longer)
...
Result: Long-term memory! 🎉
```

The system uses the **SM-2 algorithm**:

```python
def calculate_next_review(correct, current_ease_factor, current_interval):
    if correct:
        # Got it right! Increase interval
        new_ease = current_ease_factor + 0.1
        new_interval = current_interval * new_ease
    else:
        # Got it wrong! Review sooner
        new_ease = current_ease_factor - 0.2
        new_interval = 1  # Review tomorrow!

    next_review_date = today + new_interval
    return next_review_date, new_ease
```

### How Your Quiz Score Affects Learning

```
Score >= 85%  →  "You've mastered this! Let's move on to harder topics"
Score 60-84%  →  "Good progress! A few more reviews should help"
Score < 60%   →  "Let's slow down and practice these concepts more"
```

The assessment code is in: `src/modules/assessment/`

---

## 11. The Feynman Technique - Learn by Teaching

The **Feynman Technique** is named after physicist Richard Feynman. The idea: if you can explain something simply, you truly understand it.

### How It Works in the App

```
┌────────────────────────────────────────────────────────────────┐
│                    FEYNMAN DIALOGUE                             │
│                                                                 │
│  SOCRATIC AGENT: "Can you explain 'attention' to me?           │
│                   I'm smart but know nothing about ML."         │
│                                                                 │
│  YOU: "Attention is a mechanism that helps models focus         │
│        on relevant parts of the input."                         │
│                                                                 │
│  SOCRATIC: "Hmm, I'm confused. What do you mean by 'focus'?    │
│             Computers don't have eyes, right?"                  │
│                                                                 │
│  YOU: "Good question! 'Focus' means assigning higher weights   │
│        to certain inputs. Like if you're reading this          │
│        sentence, you might focus on key words."                 │
│                                                                 │
│  SOCRATIC: "Weights? How does the model decide what weight     │
│             to assign? Is it random?"                           │
│                                                                 │
│  YOU: "No, it learns which things are important through        │
│        training. It uses queries, keys, and values..."         │
│                                                                 │
│  SOCRATIC: "Wait, what's a query? Like a search query?"        │
│                                                                 │
│  ... (dialogue continues) ...                                   │
│                                                                 │
│  EVALUATION:                                                    │
│  - Completeness: 7/10 (missed some details)                    │
│  - Accuracy: 9/10 (correct explanations)                       │
│  - Simplicity: 8/10 (good analogies)                           │
│  - Gaps found: "Didn't explain softmax function"               │
└────────────────────────────────────────────────────────────────┘
```

### The Five Phases

1. **Opening** - AI asks you to explain the concept
2. **Probing** - AI asks "What do you mean by X?"
3. **Deepening** - AI asks edge cases and "what ifs"
4. **Testing** - AI asks for analogies and real examples
5. **Closing** - AI evaluates your explanation

### Why This Works

- **Forces clear thinking** - Jargon doesn't work on a "confused student"
- **Reveals gaps** - You can't explain what you don't understand
- **Active learning** - Teaching is more effective than re-reading

The Socratic agent code is in: `src/modules/agents/socratic.py`

---

## 12. Content and Vector Search

### How Content Is Stored

The app ingests learning materials from various sources:

```
Sources:
- arXiv (research papers)
- YouTube (video tutorials)
- Medium (blog posts)
- Documentation sites
```

Each piece of content is processed:

```
┌─────────────────────────────────────────────────────────────┐
│                  CONTENT INGESTION                           │
│                                                              │
│  Raw Article                                                 │
│      │                                                       │
│      ▼                                                       │
│  Extract text & metadata                                     │
│  (title, author, date)                                       │
│      │                                                       │
│      ▼                                                       │
│  Generate summary                                            │
│  (using Claude AI)                                           │
│      │                                                       │
│      ▼                                                       │
│  Create embedding                                            │
│  (convert text to numbers)                                   │
│      │                                                       │
│      ▼                                                       │
│  Store in database                                           │
│  (with vector for search)                                    │
└─────────────────────────────────────────────────────────────┘
```

### What Are Vector Embeddings?

An **embedding** is a list of numbers that represents the meaning of text:

```
"attention mechanism" → [0.12, -0.45, 0.78, ..., 0.33]  (1536 numbers)
"focus and weights"   → [0.11, -0.43, 0.79, ..., 0.32]  (similar numbers!)
"cooking recipes"     → [-0.89, 0.12, -0.34, ..., 0.87] (very different!)
```

Similar meanings = similar numbers!

### Vector Search vs Keyword Search

**Keyword Search** (traditional):
```
Query: "how attention works"
Result: Only finds documents with exact words "attention" AND "works"
```

**Vector Search** (what we use):
```
Query: "how attention works"
       ↓ (convert to embedding)
       [0.12, -0.45, ...]
       ↓ (find similar embeddings)
Results:
  1. "Understanding the attention mechanism" ✓
  2. "Query-key-value explained" ✓
  3. "Focus and concentration in neural networks" ✓
```

Vector search finds **semantically similar** content, even with different words!

### The Database Query

We use PostgreSQL with the `pgvector` extension:

```sql
-- Find 10 most similar articles to my query
SELECT title, summary
FROM content
ORDER BY embedding <=> '[0.12, -0.45, ...]'  -- <=> means "distance"
LIMIT 10;
```

The content code is in: `src/modules/content/`

---

## 13. A Complete Journey Through the App

Let's follow a user from registration to completing their first session:

### Day 1: Getting Started

```
┌────────────────────────────────────────────────────────────────┐
│ STEP 1: REGISTRATION                                           │
│                                                                 │
│ $ learner auth register                                         │
│                                                                 │
│ Email: alice@university.edu                                     │
│ Password: ********                                              │
│                                                                 │
│ What happens:                                                   │
│ 1. CLI → API: POST /auth/register                              │
│ 2. Auth Service: Hash password, create user                    │
│ 3. Database: INSERT INTO users, user_profiles, learning_patterns│
│ 4. Generate JWT tokens                                         │
│ 5. CLI: Save tokens to state.json                              │
│                                                                 │
│ Output: "Welcome, Alice! Account created successfully."         │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ STEP 2: ONBOARDING                                              │
│                                                                 │
│ $ learner profile onboarding                                    │
│                                                                 │
│ What's your background? Software Engineer                       │
│ Learning goals? Understand Transformers                         │
│ Weekly time budget? 5 hours                                     │
│ Preferred sources? arXiv, YouTube                               │
│                                                                 │
│ What happens:                                                   │
│ 1. Curriculum Agent: Creates learning path                      │
│    - Week 1: Attention basics                                   │
│    - Week 2: Transformer architecture                           │
│    - Week 3: Implementation                                     │
│    - Week 4: Applications (BERT, GPT)                          │
│ 2. Database: Update user_profiles                               │
│                                                                 │
│ Output: "Great! I've created your 4-week learning path."        │
└────────────────────────────────────────────────────────────────┘
```

### Day 1: First Learning Session

```
┌────────────────────────────────────────────────────────────────┐
│ STEP 3: START SESSION                                           │
│                                                                 │
│ $ learner start --time 30                                       │
│                                                                 │
│ What happens:                                                   │
│ 1. Session Service: Create session (status: in_progress)       │
│ 2. Get context: proficiency=0, gaps=[], streak=0               │
│ 3. Curriculum Agent: "Start with attention basics"              │
│ 4. Scout Agent: Find beginner-friendly content                  │
│ 5. Plan: 15min read + 10min quiz + 5min Feynman                │
│ 6. Coach Agent: Generate welcome                                │
│                                                                 │
│ Output:                                                         │
│ ╔══════════════════════════════════════════════════════════╗   │
│ ║  COACH: Welcome to your first session, Alice!            ║   │
│ ║                                                          ║   │
│ ║  Today's focus: Attention Mechanism Basics               ║   │
│ ║                                                          ║   │
│ ║  I've found a great visual explanation to get started.   ║   │
│ ║  Let's dive in!                                          ║   │
│ ║                                                          ║   │
│ ║  Session plan:                                           ║   │
│ ║  1. Read: "Visual Guide to Attention" (15 min)          ║   │
│ ║  2. Quiz: 5 questions (10 min)                          ║   │
│ ║  3. Explain: Feynman dialogue (5 min)                   ║   │
│ ╚══════════════════════════════════════════════════════════╝   │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ STEP 4: READING CONTENT                                         │
│                                                                 │
│ [Article displayed with formatting]                             │
│                                                                 │
│ What happens:                                                   │
│ 1. Content displayed in terminal                                │
│ 2. Timer tracks reading time                                    │
│ 3. User presses Enter when done                                 │
│ 4. Record activity: content_read, 15 min                        │
│                                                                 │
│ Database: INSERT INTO session_activities                        │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ STEP 5: QUIZ TIME                                               │
│                                                                 │
│ Assessment Agent generates quiz...                              │
│                                                                 │
│ Question 1/5:                                                   │
│ What does the attention mechanism primarily compute?            │
│   A) A weighted sum of values based on relevance                │
│   B) The maximum value in the sequence                          │
│   C) A random sample from inputs                                │
│   D) The average of all inputs                                  │
│                                                                 │
│ Your answer: A ✓                                                │
│                                                                 │
│ ... (questions 2-5) ...                                         │
│                                                                 │
│ Results:                                                        │
│ Score: 3/5 (60%)                                                │
│ Gaps identified: "Query-key-value computation unclear"          │
│                                                                 │
│ What happens:                                                   │
│ 1. Assessment Service: Evaluate answers                         │
│ 2. Update proficiency: 0 → 0.4                                  │
│ 3. Schedule review: tomorrow                                    │
│ 4. Identify gaps for follow-up                                  │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ STEP 6: FEYNMAN DIALOGUE                                        │
│                                                                 │
│ Socratic Agent: "Can you explain attention to me?"              │
│                                                                 │
│ You: "Attention helps models focus on important parts"          │
│                                                                 │
│ Socratic: "Hmm, what does 'focus' mean for a computer?"        │
│                                                                 │
│ You: "It assigns higher weights to certain inputs"              │
│                                                                 │
│ Socratic: "How does it know what weight to assign?"             │
│                                                                 │
│ You: "Through training, it learns what's relevant"              │
│                                                                 │
│ ... (dialogue continues) ...                                    │
│                                                                 │
│ Evaluation:                                                     │
│ - Completeness: 6/10                                            │
│ - Accuracy: 7/10                                                │
│ - Simplicity: 7/10                                              │
│ - Gaps: "Didn't explain query-key-value mechanism"              │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ STEP 7: SESSION END                                             │
│                                                                 │
│ $ learner session end (or time runs out)                        │
│                                                                 │
│ What happens:                                                   │
│ 1. Calculate actual duration: 32 minutes                        │
│ 2. Update learning patterns:                                    │
│    - total_sessions: 0 → 1                                      │
│    - current_streak: 0 → 1                                      │
│ 3. Update topic progress:                                       │
│    - attention: proficiency 0.4                                 │
│    - next_review: tomorrow                                      │
│ 4. Coach generates summary                                      │
│                                                                 │
│ Output:                                                         │
│ ╔══════════════════════════════════════════════════════════╗   │
│ ║  SESSION COMPLETE!                                       ║   │
│ ║                                                          ║   │
│ ║  Duration: 32 minutes                                    ║   │
│ ║  Topic: Attention Mechanism Basics                       ║   │
│ ║  Quiz score: 60%                                         ║   │
│ ║  Feynman score: 6.7/10                                   ║   │
│ ║                                                          ║   │
│ ║  Current streak: 1 day 🔥                                ║   │
│ ║                                                          ║   │
│ ║  To improve:                                             ║   │
│ ║  - Review query-key-value computation                    ║   │
│ ║  - Tomorrow: deeper dive into attention                  ║   │
│ ║                                                          ║   │
│ ║  See you tomorrow for Day 2!                             ║   │
│ ╚══════════════════════════════════════════════════════════╝   │
└────────────────────────────────────────────────────────────────┘
```

### Day 2 and Beyond

```
Each day:
1. Start session → Review due items (spaced repetition)
2. Learn new content based on curriculum
3. Quiz to verify understanding
4. Practice weak areas with Drill Sergeant
5. Feynman dialogue to deepen understanding
6. End session → Update streak, schedule reviews

Over time:
- Proficiency increases (0.4 → 0.6 → 0.8)
- Review intervals get longer (1 day → 3 days → 7 days)
- Topics get harder as you master basics
- AI adapts: slows down if struggling, speeds up if excelling
```

---

## 14. Key Programming Concepts Used

This app uses several important software engineering patterns. Understanding these will help you in your CS career!

### 1. Repository Pattern

**What it is**: Separates data access from business logic.

```python
# Bad: Business logic directly queries database
def get_user_score(user_id):
    result = db.execute("SELECT * FROM quizzes WHERE user_id = ?", user_id)
    # Business logic mixed with SQL
    return sum(q.score for q in result) / len(result)

# Good: Repository handles database, service handles logic
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

**Why it's useful**:
- Easier to test (mock the repository)
- Easier to change database (only update repository)
- Cleaner code separation

### 2. Dependency Injection

**What it is**: Instead of creating dependencies inside a class, pass them in.

```python
# Bad: Hard to test, tightly coupled
class SessionService:
    def __init__(self):
        self.db = Database()  # Creates its own dependency
        self.cache = Redis()

# Good: Dependencies passed in
class SessionService:
    def __init__(self, db, cache):
        self.db = db
        self.cache = cache

# Now you can pass mock objects for testing!
service = SessionService(mock_db, mock_cache)
```

**In FastAPI**:
```python
from fastapi import Depends

def get_session_service():
    return SessionService(db, cache)

@app.post("/sessions")
def create_session(service: SessionService = Depends(get_session_service)):
    return service.create()
```

### 3. Strategy Pattern

**What it is**: Different algorithms/behaviors that can be swapped.

```python
# Different content sources use different adapters
class SourceAdapter:
    def fetch_content(self): pass

class ArxivAdapter(SourceAdapter):
    def fetch_content(self):
        # Fetch from arXiv API
        pass

class YouTubeAdapter(SourceAdapter):
    def fetch_content(self):
        # Fetch from YouTube API
        pass

# Use any adapter interchangeably
def ingest_content(adapter: SourceAdapter):
    return adapter.fetch_content()

ingest_content(ArxivAdapter())   # Works!
ingest_content(YouTubeAdapter()) # Also works!
```

### 4. State Pattern

**What it is**: Object behavior changes based on internal state.

The Orchestrator manages conversation state:
```python
class Orchestrator:
    def __init__(self):
        self.state = "idle"

    def handle_message(self, message):
        if self.state == "idle":
            return self.start_session(message)
        elif self.state == "quiz":
            return self.handle_quiz_answer(message)
        elif self.state == "feynman":
            return self.handle_feynman_response(message)
```

### 5. Factory Pattern

**What it is**: A function that creates and returns objects.

```python
# Singleton factory - always returns the same instance
_orchestrator = None

def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator

# Always get the same orchestrator
orch1 = get_orchestrator()
orch2 = get_orchestrator()
assert orch1 is orch2  # True! Same object
```

### 6. Async/Await (Asynchronous Programming)

**What it is**: Code that doesn't block while waiting.

```python
# Synchronous (blocking) - slow!
def get_data():
    result1 = fetch_from_api_1()  # Wait 2 seconds
    result2 = fetch_from_api_2()  # Wait 2 more seconds
    return result1, result2       # Total: 4 seconds

# Asynchronous (non-blocking) - fast!
async def get_data():
    task1 = fetch_from_api_1()    # Start request
    task2 = fetch_from_api_2()    # Start request immediately
    result1, result2 = await asyncio.gather(task1, task2)
    return result1, result2       # Total: 2 seconds (parallel!)
```

The API uses FastAPI which is async by default.

---

## 15. Files to Study If You Want to Learn More

If you want to understand this codebase deeply, read these files in order:

### Start Here (Foundation)
1. **`migrations/001_initial_schema.sql`** - The database structure
2. **`src/shared/config.py`** - How configuration works
3. **`src/shared/database.py`** - Database connection setup

### Core Logic
4. **`src/modules/auth/service.py`** - Authentication logic
5. **`src/modules/session/service.py`** - Session management
6. **`src/modules/assessment/service.py`** - Quiz creation and grading

### AI Agents
7. **`src/modules/agents/orchestrator.py`** - How agents are coordinated
8. **`src/modules/agents/coach.py`** - The motivational coach
9. **`src/modules/agents/socratic.py`** - The Feynman technique agent
10. **`src/modules/agents/curriculum.py`** - Learning path planning

### Entry Points
11. **`src/api/main.py`** - How the REST API starts
12. **`src/cli/main.py`** - How the CLI works
13. **`src/cli/nlp_parser.py`** - Natural language understanding

### Testing
14. **`tests/unit/`** - How to write tests for each module
15. **`tests/integration/`** - How different parts work together

---

## Summary

This learning app is like having a **team of AI tutors** that:

1. **Plan** what you should learn (Curriculum Agent)
2. **Find** the best content for you (Scout Agent)
3. **Motivate** you to keep going (Coach Agent)
4. **Test** your knowledge (Assessment Agent)
5. **Challenge** your understanding (Socratic Agent)
6. **Drill** your weak points (Drill Sergeant Agent)

Behind the scenes, it uses:
- **PostgreSQL** database to store everything
- **Vector embeddings** to find similar content
- **JWT tokens** for secure login
- **Spaced repetition** so you remember long-term
- **FastAPI** for the REST API
- **Typer/Rich** for the beautiful CLI

The code is organized into **modules** (auth, session, content, etc.), each with its own **service** (business logic) and **repository** (database access).

This is a real-world, production-quality application that demonstrates many concepts you'll learn throughout your CS degree!

---

## Quick Reference

### Run the App
```bash
# Install dependencies
pip install -r requirements.txt

# Start the API server
uvicorn src.api.main:app --reload

# Use the CLI
python -m src.cli.main --help
```

### Key Technologies
| Technology | Purpose |
|-----------|---------|
| Python 3.11+ | Main programming language |
| FastAPI | REST API framework |
| PostgreSQL | Database |
| pgvector | Vector similarity search |
| Redis | Caching and state |
| Claude AI | Powers the AI agents |
| Typer | CLI framework |
| Rich | Pretty terminal output |
| bcrypt | Password hashing |
| JWT | Authentication tokens |

---

*This guide was written to help first-year CS students understand how a modern, production-quality application works. Don't worry if some concepts seem complex - they'll make more sense as you progress through your studies!*
