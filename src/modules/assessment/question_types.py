"""Enhanced question type generators for assessments.

This module provides sophisticated question generators that go beyond
simple factual recall, including:
- Scenario-based questions
- Comparison questions
- Application questions
- Synthesis questions

These question types align with Bloom's taxonomy higher-order thinking levels.
"""

import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class QuestionDifficulty(Enum):
    """Question difficulty levels based on cognitive load."""
    RECALL = "recall"           # Remember facts
    UNDERSTAND = "understand"   # Explain concepts
    APPLY = "apply"            # Use in new situations
    ANALYZE = "analyze"        # Break down and examine
    EVALUATE = "evaluate"      # Judge and critique
    CREATE = "create"          # Generate new ideas


class QuestionType(Enum):
    """Types of questions supported by the system."""
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    SHORT_ANSWER = "short_answer"
    SCENARIO = "scenario"
    COMPARISON = "comparison"
    APPLICATION = "application"
    SYNTHESIS = "synthesis"


@dataclass
class QuestionOption:
    """An option for multiple-choice questions."""
    text: str
    is_correct: bool
    explanation: Optional[str] = None


@dataclass
class GeneratedQuestion:
    """A generated assessment question."""
    question_type: QuestionType
    difficulty: QuestionDifficulty
    text: str
    topic: str
    options: list[QuestionOption] = field(default_factory=list)
    correct_answer: Optional[str] = None
    explanation: str = ""
    hints: list[str] = field(default_factory=list)
    context: Optional[str] = None  # For scenario questions
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        return {
            'question_type': self.question_type.value,
            'difficulty': self.difficulty.value,
            'text': self.text,
            'topic': self.topic,
            'options': [
                {'text': o.text, 'is_correct': o.is_correct, 'explanation': o.explanation}
                for o in self.options
            ],
            'correct_answer': self.correct_answer,
            'explanation': self.explanation,
            'hints': self.hints,
            'context': self.context,
            'metadata': self.metadata,
        }


class QuestionGenerator(ABC):
    """Abstract base class for question generators."""

    @abstractmethod
    async def generate(
        self,
        topic: str,
        difficulty: QuestionDifficulty,
        context: Optional[dict[str, Any]] = None,
    ) -> GeneratedQuestion:
        """Generate a question for the given topic and difficulty.

        Args:
            topic: The topic to generate a question about.
            difficulty: The target difficulty level.
            context: Optional context information for personalization.

        Returns:
            A generated question.
        """
        pass

    @property
    @abstractmethod
    def question_type(self) -> QuestionType:
        """The type of question this generator produces."""
        pass


class ScenarioQuestionGenerator(QuestionGenerator):
    """Generator for scenario-based questions.

    Scenario questions present a realistic situation and ask the learner
    to apply their knowledge to solve a problem or make a decision.

    Example:
        "You're building a recommendation system for an e-commerce site.
        Users are complaining that recommendations are too similar to
        items they've already purchased. Which technique would BEST
        address this issue?"
    """

    def __init__(self, llm_service=None):
        """Initialize the generator.

        Args:
            llm_service: Optional LLM service for dynamic generation.
        """
        self._llm = llm_service

    @property
    def question_type(self) -> QuestionType:
        return QuestionType.SCENARIO

    async def generate(
        self,
        topic: str,
        difficulty: QuestionDifficulty,
        context: Optional[dict[str, Any]] = None,
    ) -> GeneratedQuestion:
        """Generate a scenario-based question."""
        context = context or {}

        # Use LLM if available for dynamic generation
        if self._llm:
            return await self._generate_with_llm(topic, difficulty, context)

        # Fall back to template-based generation
        return self._generate_from_template(topic, difficulty, context)

    async def _generate_with_llm(
        self,
        topic: str,
        difficulty: QuestionDifficulty,
        context: dict[str, Any],
    ) -> GeneratedQuestion:
        """Generate question using LLM."""
        prompt = self._build_prompt(topic, difficulty, context)

        response = await self._llm.complete(prompt)
        return self._parse_llm_response(response, topic, difficulty)

    def _build_prompt(
        self,
        topic: str,
        difficulty: QuestionDifficulty,
        context: dict[str, Any],
    ) -> str:
        """Build the LLM prompt for scenario generation."""
        user_level = context.get('user_level', 'intermediate')
        domain = context.get('domain', 'technology')

        return f"""Generate a scenario-based assessment question about {topic}.

Difficulty Level: {difficulty.value}
User Level: {user_level}
Domain Context: {domain}

Requirements:
1. Create a realistic scenario that a professional might encounter
2. The scenario should test application of knowledge, not just recall
3. Include 4 multiple-choice options with one clearly correct answer
4. Each incorrect option should be plausible but have a specific flaw
5. Provide an explanation for why the correct answer is best

Output format (JSON):
{{
    "scenario": "Description of the realistic situation...",
    "question": "What should you do / Which approach is best...",
    "options": [
        {{"text": "Option A", "is_correct": false, "explanation": "Why this is not ideal"}},
        {{"text": "Option B", "is_correct": true, "explanation": "Why this is correct"}},
        {{"text": "Option C", "is_correct": false, "explanation": "Why this is not ideal"}},
        {{"text": "Option D", "is_correct": false, "explanation": "Why this is not ideal"}}
    ],
    "explanation": "Detailed explanation of the correct approach",
    "hints": ["Hint 1", "Hint 2"]
}}"""

    def _parse_llm_response(
        self,
        response: Any,
        topic: str,
        difficulty: QuestionDifficulty,
    ) -> GeneratedQuestion:
        """Parse LLM response into a GeneratedQuestion."""
        import json

        try:
            data = json.loads(response.content)
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response as JSON")
            raise ValueError("Invalid LLM response format")

        options = [
            QuestionOption(
                text=opt['text'],
                is_correct=opt['is_correct'],
                explanation=opt.get('explanation'),
            )
            for opt in data['options']
        ]

        correct_answer = next(
            (opt['text'] for opt in data['options'] if opt['is_correct']),
            None
        )

        return GeneratedQuestion(
            question_type=QuestionType.SCENARIO,
            difficulty=difficulty,
            text=data['question'],
            topic=topic,
            options=options,
            correct_answer=correct_answer,
            explanation=data.get('explanation', ''),
            hints=data.get('hints', []),
            context=data.get('scenario'),
        )

    def _generate_from_template(
        self,
        topic: str,
        difficulty: QuestionDifficulty,
        context: dict[str, Any],
    ) -> GeneratedQuestion:
        """Generate question from templates when LLM unavailable."""
        # Template-based scenarios for common topics
        templates = self._get_scenario_templates(topic)

        if not templates:
            # Generic fallback
            return self._generate_generic_scenario(topic, difficulty)

        template = random.choice(templates)
        return self._fill_template(template, topic, difficulty)

    def _get_scenario_templates(self, topic: str) -> list[dict]:
        """Get scenario templates for a topic."""
        # This would typically load from a database or file
        # Simplified inline templates for common ML/AI topics
        templates_by_topic = {
            'neural_networks': [
                {
                    'scenario': "You're training a neural network for image classification, "
                               "but validation loss starts increasing while training loss "
                               "continues to decrease after epoch 15.",
                    'question': "What is the most likely issue and best solution?",
                    'options': [
                        {'text': 'Increase learning rate to speed up convergence',
                         'is_correct': False,
                         'explanation': 'This would likely make overfitting worse'},
                        {'text': 'Add dropout layers and implement early stopping',
                         'is_correct': True,
                         'explanation': 'Addresses overfitting with regularization'},
                        {'text': 'Add more layers to increase model capacity',
                         'is_correct': False,
                         'explanation': 'More capacity would increase overfitting'},
                        {'text': 'Remove the validation set to eliminate the gap',
                         'is_correct': False,
                         'explanation': 'This hides the problem rather than solving it'},
                    ],
                    'explanation': 'The divergence between training and validation loss '
                                  'indicates overfitting. Dropout provides regularization '
                                  'and early stopping prevents training past the optimal point.',
                    'hints': ['Consider what the gap between losses indicates',
                              'Think about regularization techniques'],
                },
            ],
            'transformers': [
                {
                    'scenario': "You're fine-tuning a BERT model for sentiment analysis "
                               "on customer reviews. The model performs well on product "
                               "reviews but poorly on service-related reviews.",
                    'question': "What approach would most likely improve performance?",
                    'options': [
                        {'text': 'Increase the number of training epochs',
                         'is_correct': False,
                         'explanation': 'More epochs won\'t help with distribution mismatch'},
                        {'text': 'Add more service-related reviews to training data',
                         'is_correct': True,
                         'explanation': 'Addresses the data imbalance directly'},
                        {'text': 'Use a larger BERT variant',
                         'is_correct': False,
                         'explanation': 'Model size doesn\'t address data distribution'},
                        {'text': 'Reduce the sequence length',
                         'is_correct': False,
                         'explanation': 'Would lose important context'},
                    ],
                    'explanation': 'The performance gap suggests the training data is '
                                  'imbalanced toward product reviews. Adding more diverse '
                                  'service-related examples directly addresses this gap.',
                    'hints': ['Consider what\'s different about the two review types',
                              'Think about your training data composition'],
                },
            ],
        }

        # Normalize topic for lookup
        normalized = topic.lower().replace(' ', '_').replace('-', '_')
        return templates_by_topic.get(normalized, [])

    def _fill_template(
        self,
        template: dict,
        topic: str,
        difficulty: QuestionDifficulty,
    ) -> GeneratedQuestion:
        """Fill a template to create a question."""
        options = [
            QuestionOption(
                text=opt['text'],
                is_correct=opt['is_correct'],
                explanation=opt.get('explanation'),
            )
            for opt in template['options']
        ]

        correct_answer = next(
            (opt['text'] for opt in template['options'] if opt['is_correct']),
            None
        )

        return GeneratedQuestion(
            question_type=QuestionType.SCENARIO,
            difficulty=difficulty,
            text=template['question'],
            topic=topic,
            options=options,
            correct_answer=correct_answer,
            explanation=template.get('explanation', ''),
            hints=template.get('hints', []),
            context=template.get('scenario'),
        )

    def _generate_generic_scenario(
        self,
        topic: str,
        difficulty: QuestionDifficulty,
    ) -> GeneratedQuestion:
        """Generate a generic scenario when no template exists."""
        return GeneratedQuestion(
            question_type=QuestionType.SCENARIO,
            difficulty=difficulty,
            text=f"In a real-world application of {topic}, what would be the most "
                 f"important consideration for production deployment?",
            topic=topic,
            options=[
                QuestionOption("Performance optimization", False,
                              "Important but not always the primary concern"),
                QuestionOption("Scalability and maintainability", True,
                              "Critical for long-term success"),
                QuestionOption("Using the latest frameworks", False,
                              "Novelty shouldn't drive architecture decisions"),
                QuestionOption("Minimizing development time", False,
                              "Short-term speed can cause long-term problems"),
            ],
            correct_answer="Scalability and maintainability",
            explanation="While all factors matter, production systems must be "
                       "designed for long-term scalability and maintainability "
                       "to handle evolving requirements.",
            hints=["Think about what makes systems successful over time",
                   "Consider the full lifecycle of a production system"],
            context=f"You're designing a production system that uses {topic}.",
        )


class ComparisonQuestionGenerator(QuestionGenerator):
    """Generator for comparison questions.

    Comparison questions ask learners to identify similarities, differences,
    or trade-offs between related concepts.

    Example:
        "Compare batch normalization and layer normalization.
        In which scenario would layer normalization be preferred?"
    """

    def __init__(self, llm_service=None):
        """Initialize the generator."""
        self._llm = llm_service

    @property
    def question_type(self) -> QuestionType:
        return QuestionType.COMPARISON

    async def generate(
        self,
        topic: str,
        difficulty: QuestionDifficulty,
        context: Optional[dict[str, Any]] = None,
    ) -> GeneratedQuestion:
        """Generate a comparison question."""
        context = context or {}

        if self._llm:
            return await self._generate_with_llm(topic, difficulty, context)

        return self._generate_from_template(topic, difficulty, context)

    async def _generate_with_llm(
        self,
        topic: str,
        difficulty: QuestionDifficulty,
        context: dict[str, Any],
    ) -> GeneratedQuestion:
        """Generate comparison question using LLM."""
        prompt = f"""Generate a comparison question about {topic}.

Difficulty: {difficulty.value}

Create a question that asks the learner to compare two related concepts,
techniques, or approaches. The question should test understanding of
trade-offs and appropriate use cases.

Output format (JSON):
{{
    "concept_a": "First concept being compared",
    "concept_b": "Second concept being compared",
    "question": "The comparison question",
    "options": [
        {{"text": "Option text", "is_correct": true/false, "explanation": "Why"}}
    ],
    "explanation": "Detailed comparison and answer explanation",
    "hints": ["Hint 1", "Hint 2"]
}}"""

        response = await self._llm.complete(prompt)
        return self._parse_llm_response(response, topic, difficulty)

    def _parse_llm_response(
        self,
        response: Any,
        topic: str,
        difficulty: QuestionDifficulty,
    ) -> GeneratedQuestion:
        """Parse LLM response into a GeneratedQuestion."""
        import json

        data = json.loads(response.content)

        options = [
            QuestionOption(
                text=opt['text'],
                is_correct=opt['is_correct'],
                explanation=opt.get('explanation'),
            )
            for opt in data['options']
        ]

        correct_answer = next(
            (opt['text'] for opt in data['options'] if opt['is_correct']),
            None
        )

        return GeneratedQuestion(
            question_type=QuestionType.COMPARISON,
            difficulty=difficulty,
            text=data['question'],
            topic=topic,
            options=options,
            correct_answer=correct_answer,
            explanation=data.get('explanation', ''),
            hints=data.get('hints', []),
            metadata={
                'concept_a': data.get('concept_a'),
                'concept_b': data.get('concept_b'),
            },
        )

    def _generate_from_template(
        self,
        topic: str,
        difficulty: QuestionDifficulty,
        context: dict[str, Any],
    ) -> GeneratedQuestion:
        """Generate from templates when LLM unavailable."""
        comparisons = self._get_comparison_pairs(topic)

        if not comparisons:
            return self._generate_generic_comparison(topic, difficulty)

        pair = random.choice(comparisons)
        return self._create_comparison_question(pair, topic, difficulty)

    def _get_comparison_pairs(self, topic: str) -> list[dict]:
        """Get comparison pairs for a topic."""
        pairs_by_topic = {
            'normalization': [
                {
                    'concept_a': 'Batch Normalization',
                    'concept_b': 'Layer Normalization',
                    'question': 'When would Layer Normalization be preferred over '
                               'Batch Normalization?',
                    'options': [
                        {'text': 'When training with very large batch sizes',
                         'is_correct': False,
                         'explanation': 'Large batches favor batch normalization'},
                        {'text': 'When working with sequence models like Transformers',
                         'is_correct': True,
                         'explanation': 'Layer norm is independent of batch size'},
                        {'text': 'When computational resources are limited',
                         'is_correct': False,
                         'explanation': 'Both have similar computational costs'},
                        {'text': 'When using convolutional networks for images',
                         'is_correct': False,
                         'explanation': 'CNNs typically use batch normalization'},
                    ],
                    'explanation': 'Layer Normalization normalizes across features '
                                  'rather than the batch dimension, making it ideal '
                                  'for sequence models where batch statistics vary.',
                },
            ],
            'optimizers': [
                {
                    'concept_a': 'Adam',
                    'concept_b': 'SGD with Momentum',
                    'question': 'In which scenario might SGD with momentum outperform Adam?',
                    'options': [
                        {'text': 'When training on very small datasets',
                         'is_correct': False,
                         'explanation': 'Adam\'s adaptivity helps with small data'},
                        {'text': 'When maximum generalization is critical',
                         'is_correct': True,
                         'explanation': 'SGD often generalizes better'},
                        {'text': 'When training large language models from scratch',
                         'is_correct': False,
                         'explanation': 'Adam is typically preferred for LLMs'},
                        {'text': 'When dealing with sparse gradients',
                         'is_correct': False,
                         'explanation': 'Adam handles sparse gradients better'},
                    ],
                    'explanation': 'Research shows SGD with momentum often finds '
                                  'solutions that generalize better to test data, '
                                  'though it may require more careful tuning.',
                },
            ],
        }

        normalized = topic.lower().replace(' ', '_').replace('-', '_')
        return pairs_by_topic.get(normalized, [])

    def _create_comparison_question(
        self,
        pair: dict,
        topic: str,
        difficulty: QuestionDifficulty,
    ) -> GeneratedQuestion:
        """Create a question from a comparison pair."""
        options = [
            QuestionOption(
                text=opt['text'],
                is_correct=opt['is_correct'],
                explanation=opt.get('explanation'),
            )
            for opt in pair['options']
        ]

        correct_answer = next(
            (opt['text'] for opt in pair['options'] if opt['is_correct']),
            None
        )

        return GeneratedQuestion(
            question_type=QuestionType.COMPARISON,
            difficulty=difficulty,
            text=pair['question'],
            topic=topic,
            options=options,
            correct_answer=correct_answer,
            explanation=pair.get('explanation', ''),
            hints=pair.get('hints', []),
            metadata={
                'concept_a': pair['concept_a'],
                'concept_b': pair['concept_b'],
            },
        )

    def _generate_generic_comparison(
        self,
        topic: str,
        difficulty: QuestionDifficulty,
    ) -> GeneratedQuestion:
        """Generate a generic comparison question."""
        return GeneratedQuestion(
            question_type=QuestionType.COMPARISON,
            difficulty=difficulty,
            text=f"What is the primary trade-off to consider when choosing "
                 f"different approaches within {topic}?",
            topic=topic,
            options=[
                QuestionOption("Speed vs accuracy", False,
                              "One common trade-off but not universal"),
                QuestionOption("Complexity vs interpretability", True,
                              "Fundamental trade-off across many domains"),
                QuestionOption("Cost vs quality", False,
                              "More of a resource constraint"),
                QuestionOption("Old vs new techniques", False,
                              "Age isn't a meaningful trade-off dimension"),
            ],
            correct_answer="Complexity vs interpretability",
            explanation="The trade-off between model/system complexity and "
                       "interpretability is fundamental across ML and software "
                       "engineering, affecting debugging, trust, and maintenance.",
            hints=["Think about what you lose as systems get more complex",
                   "Consider the human factors in technical decisions"],
        )


class ApplicationQuestionGenerator(QuestionGenerator):
    """Generator for application questions.

    Application questions test the ability to apply learned concepts
    to solve specific problems.
    """

    def __init__(self, llm_service=None):
        """Initialize the generator."""
        self._llm = llm_service

    @property
    def question_type(self) -> QuestionType:
        return QuestionType.APPLICATION

    async def generate(
        self,
        topic: str,
        difficulty: QuestionDifficulty,
        context: Optional[dict[str, Any]] = None,
    ) -> GeneratedQuestion:
        """Generate an application question."""
        context = context or {}

        # Application questions focus on "how to use" knowledge
        templates = self._get_application_templates(topic)

        if templates:
            template = random.choice(templates)
            return self._fill_template(template, topic, difficulty)

        return self._generate_generic_application(topic, difficulty)

    def _get_application_templates(self, topic: str) -> list[dict]:
        """Get application templates for a topic."""
        templates_by_topic = {
            'attention': [
                {
                    'problem': "You need to build a model that processes "
                              "documents of varying lengths efficiently.",
                    'question': "How would you apply attention mechanisms "
                               "to handle variable-length input?",
                    'options': [
                        {'text': 'Use fixed-size padding for all documents',
                         'is_correct': False,
                         'explanation': 'Wasteful and doesn\'t leverage attention'},
                        {'text': 'Apply attention masks to handle varying lengths',
                         'is_correct': True,
                         'explanation': 'Standard approach for variable sequences'},
                        {'text': 'Truncate all documents to minimum length',
                         'is_correct': False,
                         'explanation': 'Loses important information'},
                        {'text': 'Process each word independently',
                         'is_correct': False,
                         'explanation': 'Ignores contextual relationships'},
                    ],
                    'explanation': 'Attention masks allow models to process '
                                  'variable-length sequences by masking padding '
                                  'tokens, maintaining computational efficiency.',
                },
            ],
        }

        normalized = topic.lower().replace(' ', '_').replace('-', '_')
        return templates_by_topic.get(normalized, [])

    def _fill_template(
        self,
        template: dict,
        topic: str,
        difficulty: QuestionDifficulty,
    ) -> GeneratedQuestion:
        """Fill a template to create a question."""
        options = [
            QuestionOption(
                text=opt['text'],
                is_correct=opt['is_correct'],
                explanation=opt.get('explanation'),
            )
            for opt in template['options']
        ]

        correct_answer = next(
            (opt['text'] for opt in template['options'] if opt['is_correct']),
            None
        )

        return GeneratedQuestion(
            question_type=QuestionType.APPLICATION,
            difficulty=difficulty,
            text=template['question'],
            topic=topic,
            options=options,
            correct_answer=correct_answer,
            explanation=template.get('explanation', ''),
            hints=template.get('hints', []),
            context=template.get('problem'),
        )

    def _generate_generic_application(
        self,
        topic: str,
        difficulty: QuestionDifficulty,
    ) -> GeneratedQuestion:
        """Generate a generic application question."""
        return GeneratedQuestion(
            question_type=QuestionType.APPLICATION,
            difficulty=difficulty,
            text=f"You need to implement a solution using {topic}. "
                 f"What would be your first step?",
            topic=topic,
            options=[
                QuestionOption("Start coding immediately", False,
                              "May lead to rework without understanding"),
                QuestionOption("Understand the problem requirements first", True,
                              "Essential foundation for any implementation"),
                QuestionOption("Copy existing code from the internet", False,
                              "May not fit your specific requirements"),
                QuestionOption("Ask someone else to do it", False,
                              "Doesn't develop your own understanding"),
            ],
            correct_answer="Understand the problem requirements first",
            explanation="Effective application of any technique requires "
                       "first understanding what problem you're solving "
                       "and how the technique addresses that need.",
            hints=["Think about what comes before implementation",
                   "Consider how experts approach new problems"],
        )


class QuestionGeneratorFactory:
    """Factory for creating question generators."""

    _generators: dict[QuestionType, type[QuestionGenerator]] = {
        QuestionType.SCENARIO: ScenarioQuestionGenerator,
        QuestionType.COMPARISON: ComparisonQuestionGenerator,
        QuestionType.APPLICATION: ApplicationQuestionGenerator,
    }

    @classmethod
    def create(
        cls,
        question_type: QuestionType,
        llm_service=None,
    ) -> QuestionGenerator:
        """Create a question generator for the specified type.

        Args:
            question_type: The type of questions to generate.
            llm_service: Optional LLM service for dynamic generation.

        Returns:
            A question generator instance.

        Raises:
            ValueError: If question type is not supported.
        """
        generator_class = cls._generators.get(question_type)
        if generator_class is None:
            raise ValueError(f"Unsupported question type: {question_type}")

        return generator_class(llm_service=llm_service)

    @classmethod
    def get_supported_types(cls) -> list[QuestionType]:
        """Get list of supported question types."""
        return list(cls._generators.keys())


async def generate_mixed_questions(
    topic: str,
    count: int = 5,
    difficulty: QuestionDifficulty = QuestionDifficulty.APPLY,
    llm_service=None,
) -> list[GeneratedQuestion]:
    """Generate a mixed set of questions for a topic.

    Creates questions of different types to test various cognitive skills.

    Args:
        topic: The topic to generate questions about.
        count: Number of questions to generate.
        difficulty: Target difficulty level.
        llm_service: Optional LLM service for dynamic generation.

    Returns:
        List of generated questions.
    """
    questions = []
    types = QuestionGeneratorFactory.get_supported_types()

    for i in range(count):
        # Rotate through question types
        q_type = types[i % len(types)]
        generator = QuestionGeneratorFactory.create(q_type, llm_service)

        try:
            question = await generator.generate(topic, difficulty)
            questions.append(question)
        except Exception as e:
            logger.warning(f"Failed to generate {q_type.value} question: {e}")

    return questions
