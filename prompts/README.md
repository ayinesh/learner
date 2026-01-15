# Prompt Templates for AI Learning System

This directory contains all prompt templates used by the various AI agents in the learning system. Each template follows a standardized format and is designed to implement specific pedagogical principles.

## Template Format

All prompt templates use the following structure:

```
---SYSTEM---
System prompt defining agent's role, behavior, and constraints

---USER---
User prompt template with {{variable}} placeholders

---VARIABLES---
variable1, variable2, variable3
```

## Directory Structure

```
prompts/
├── socratic/           # Socratic method prompts (Feynman technique)
├── assessment/         # Quiz generation and evaluation
├── coach/             # Session management and motivation
├── curriculum/        # Learning path planning
├── scout/             # Content discovery and filtering
└── drill_sergeant/    # Targeted practice and skill building
```

## Socratic Method Prompts

These prompts implement the Socratic method for Feynman dialogues, where the AI plays a "confused student" who probes the learner's understanding through strategic questioning.

### `confused_student.txt`
**Purpose**: Initial Feynman dialogue setup
**Agent**: Socratic Agent
**Use Case**: Starting a Feynman dialogue session
**Key Features**:
- Establishes curious, intelligent persona with no AI background
- Asks "dumb questions" that reveal deep understanding gaps
- Never accepts jargon without explanation
- Focuses on strategic knowledge (when/why, not just what)

**Variables**: `topic`

### `probe_deeper.txt`
**Purpose**: Follow-up questioning on specific explanations
**Agent**: Socratic Agent
**Use Case**: After learner provides initial explanation
**Key Features**:
- Challenges specific assumptions
- Tests edge cases
- Demands concrete examples
- Questions trade-offs and limitations
- References specific points from previous explanation

**Variables**: `topic, previous_explanation, key_points`

### `test_understanding.txt`
**Purpose**: Scenario-based comprehension testing
**Agent**: Socratic Agent
**Use Case**: Verifying learner can apply knowledge
**Key Features**:
- Proposes realistic scenarios
- Asks for predictions and explanations
- Tests boundary conditions
- Includes constraints and context
- Requires application, not recitation

**Variables**: `topic, dialogue_summary`

### `strategic_questioning.txt`
**Purpose**: Explore when/why to use concepts (strategic understanding)
**Agent**: Socratic Agent
**Use Case**: After basic understanding is established
**Key Features**:
- Focuses on decision criteria
- Explores trade-offs
- Questions context dependencies
- Probes for cost-benefit analysis
- Uncovers common mistakes

**Variables**: `topic, dialogue_summary`

### `analogy_testing.txt`
**Purpose**: Build and test mental models through analogies
**Agent**: Socratic Agent
**Use Case**: Developing intuitive understanding
**Key Features**:
- Requests analogies to familiar concepts
- Tests analogy boundaries
- Identifies where comparisons break down
- Proposes alternative analogies
- Maps specific aspects to analogies

**Variables**: `topic, analogy_provided, analogy, key_aspect_1, edge_case, dialogue_summary`

### `connection_building.txt`
**Purpose**: Connect new concepts to existing knowledge
**Agent**: Socratic Agent
**Use Case**: Integrating knowledge into broader framework
**Key Features**:
- Links to prerequisites and related concepts
- Finds contrasts and similarities
- Identifies hierarchies
- Explores applications
- Builds conceptual bridges

**Variables**: `topic, related_concepts, dialogue_summary, domain`

## Assessment Prompts

Prompts for generating quizzes, evaluating understanding, and providing feedback.

### `quiz_generation.txt`
**Purpose**: Generate retrieval practice questions
**Agent**: Assessment Agent
**Use Case**: Creating quizzes for spaced repetition
**Key Features**:
- Tests genuine understanding, not recognition
- Targets strategic knowledge
- Varies question formats
- Calibrates to proficiency level
- Includes plausible distractors

**Variables**: `question_count, topics, proficiency_level, recent_content, new_count, review_count`

### `feynman_evaluation.txt`
**Purpose**: Evaluate Feynman dialogue explanations
**Agent**: Assessment Agent
**Use Case**: Scoring understanding after Feynman session
**Key Features**:
- Evaluates completeness, accuracy, simplicity
- Identifies specific gaps
- Provides concrete suggestions
- Recommends follow-up topics
- Uses 0-1 scoring scale

**Variables**: `topic, dialogue_history`

### `adaptive_difficulty.txt`
**Purpose**: Generate next quiz question with adaptive difficulty
**Agent**: Assessment Agent
**Use Case**: Creating questions that maintain optimal challenge
**Key Features**:
- Adjusts difficulty based on performance
- Targets 70-80% success rate
- Considers speed and confidence
- Provides detailed difficulty reasoning
- Uses 5-level difficulty scale

**Variables**: `proficiency_level, recent_performance, topics_covered, recent_quiz_results, recent_accuracy, avg_time_seconds, confidence_pattern, target_topic, question_type`

## Coach Prompts

Motivational and session management prompts.

### `session_opening.txt`
**Purpose**: Open learning sessions
**Agent**: Coach Agent
**Use Case**: Starting a learning session
**Key Features**:
- Acknowledges context (streak, progress, gap)
- Sets positive tone
- Helps mental transition to focus mode
- Previews session without overwhelming
- Warm but not saccharine

**Variables**: `user_name, days_since_last, current_streak, longest_streak, available_minutes, session_type, topics_preview, has_reviews, last_quiz_score, last_feynman_score`

### `session_closing.txt`
**Purpose**: Close learning sessions
**Agent**: Coach Agent
**Use Case**: Ending a learning session
**Key Features**:
- Acknowledges specific accomplishments
- Reinforces key learning
- Previews next session
- Provides genuine encouragement
- Brief and specific

**Variables**: `session_minutes, topics_covered, activities_completed, quiz_results, feynman_score, challenges, breakthroughs, topics_mastered, skills_practiced, goal_progress, current_streak, total_sessions, next_session_time, review_items_count, next_topic, upcoming_milestone`

### `recovery_plan.txt`
**Purpose**: Help users return after missed sessions
**Agent**: Coach Agent
**Use Case**: Resuming after gap in learning
**Key Features**:
- Non-judgmental acknowledgment
- Realistic retention assessment
- Structured recovery plan
- Immediate actionable steps
- Timeline impact analysis

**Variables**: `days_missed, previous_streak, longest_previous_gap, last_session_topic, topics_before_gap, last_quiz_score, last_feynman_score, proficiency_before_gap, gap_reason, available_minutes, next_milestone, days_to_milestone, current_phase, phase_progress, planned_topics`

## Curriculum Prompts

Learning path planning and topic recommendation.

### `learning_path.txt`
**Purpose**: Design personalized learning paths
**Agent**: Curriculum Agent
**Use Case**: Creating initial learning plan or major replanning
**Key Features**:
- Applies Ultralearning principles
- Sequences from prerequisites to advanced
- Allocates time realistically
- Includes practice projects
- Defines success criteria

**Variables**: `background, goals, hours_per_week, duration_weeks, learning_preferences, prior_knowledge, session_minutes, content_preferences, specific_interests, motivation, target_outcome, deadline`

### `next_topic.txt`
**Purpose**: Recommend next topic for current session
**Agent**: Curriculum Agent
**Use Case**: Deciding what to learn next
**Key Features**:
- Considers multiple decision factors
- Checks prerequisites
- Aligns with goals
- Adapts to performance
- Respects time constraints

**Variables**: `user_id, session_minutes, energy_level, topic_proficiencies, recent_topics, identified_gaps, review_items_due, recent_quiz_scores, last_feynman_score, struggle_areas, strong_areas, current_phase, planned_topics, user_goals, days_to_milestone, days_since_last, time_of_day, session_type_preference`

## Scout Prompts

Content discovery, filtering, and summarization.

### `content_relevance.txt`
**Purpose**: Evaluate content relevance to learner
**Agent**: Scout Agent
**Use Case**: Filtering content from various sources
**Key Features**:
- Multi-dimensional relevance scoring
- Timing assessment (too early/just right/later)
- Prerequisite checking
- Practical value evaluation
- Recommended action (read now/save/skip)

**Variables**: `content_title, content_source, content_type, content_summary, content_topics, content_difficulty, content_length, user_goals, current_phase, current_topics, user_proficiency, user_gaps, user_interests, available_time, backlog_size, upcoming_milestones, priority_topics`

### `content_summarization.txt`
**Purpose**: Create learning-optimized content summaries
**Agent**: Scout Agent
**Use Case**: Summarizing papers, articles, videos
**Key Features**:
- Key ideas first
- Actionable takeaways
- Prerequisite clarity
- Concrete examples
- Follow-up questions

**Variables**: `content_title, content_source, content_type, content_text, user_level, user_background, user_goals, target_length, focus_areas, include_code`

## Drill Sergeant Prompts

Targeted practice and skill building.

### `targeted_practice.txt`
**Purpose**: Design focused drills for weak spots
**Agent**: Drill Sergeant Agent
**Use Case**: Addressing identified knowledge gaps
**Key Features**:
- Laser-focused on specific weakness
- Deliberate practice principles
- Immediate feedback
- Progressive difficulty
- Mastery-based progression

**Variables**: `topic_name, specific_gap, gap_source, severity, evidence, current_proficiency, related_proficiency, recent_mistakes, error_pattern, available_minutes, energy_level, previous_attempts, learning_style, target_proficiency, mastery_threshold`

### `skill_building_project.txt`
**Purpose**: Design hands-on skill-building projects
**Agent**: Drill Sergeant Agent
**Use Case**: Applying knowledge through realistic projects
**Key Features**:
- Realistic scenarios
- Clear deliverables
- Checkpoint-based validation
- Scaffolded guidance
- Extension options

**Variables**: `recent_topics, proficiency_levels, knowledge_gaps, learning_goals, available_hours, skill_level, project_type_preference, available_resources, primary_skills, supporting_skills, integration_goals, previous_projects, current_phase, next_milestone`

## Pedagogical Principles

These prompts implement evidence-based learning science:

### From "Learning How to Learn" (Oakley)
- **Focused and Diffuse Modes**: Session structure alternates focus and practice
- **Chunking**: Topics broken into digestible concepts
- **Recall and Retrieval**: Spaced repetition quizzes
- **Interleaving**: Mixing related topics
- **Avoiding Illusions of Competence**: Feynman technique forces articulation

### From "Ultralearning" (Young)
- **Metalearning**: Curriculum planning maps learning landscape
- **Focus**: Coach prompts help transition to focused mode
- **Directness**: Skill-building projects practice target skills directly
- **Drill**: Targeted practice on weak spots
- **Retrieval**: Quiz generation emphasizes recall
- **Feedback**: Immediate, specific feedback in all assessments
- **Retention**: Spaced repetition scheduling
- **Intuition**: Socratic questioning builds deep understanding
- **Experimentation**: Projects include extension options

### Feynman Technique
- Explain in simple language
- Identify gaps through teaching
- Review and simplify
- Use analogies and examples

## Usage in Code

Templates are loaded and rendered by the LLM service:

```python
from src.modules.llm.service import get_llm_service

llm = get_llm_service()

# Load and render template
response = await llm.render_template(
    template_path="prompts/socratic/confused_student.txt",
    variables={"topic": "attention mechanisms"}
)
```

## Adding New Templates

When creating new templates:

1. **Follow the standard format**: `---SYSTEM---`, `---USER---`, `---VARIABLES---`
2. **Document the purpose**: What is this template for?
3. **Specify all variables**: List them in `---VARIABLES---` section
4. **Include pedagogical rationale**: Why this approach?
5. **Provide examples**: Show expected inputs/outputs
6. **Update this README**: Add entry in appropriate section

## Testing Templates

Templates should be tested with:
- Edge cases (empty variables, very long content)
- Different user levels (beginner to expert)
- Various contexts (first session, return after gap, etc.)
- Representative variables from actual use cases

## Version Control

- Templates are versioned with the codebase
- Breaking changes to variables require interface updates
- Template improvements should be backward compatible when possible
- Document changes in commit messages

## References

- Oakley, B. (2014). *A Mind for Numbers: How to Excel at Math and Science*
- Young, S. (2019). *Ultralearning: Master Hard Skills, Outsmart the Competition, and Accelerate Your Career*
- Feynman, R. (1985). *"Surely You're Joking, Mr. Feynman!": Adventures of a Curious Character*
