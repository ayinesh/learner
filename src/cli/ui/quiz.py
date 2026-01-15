"""Quiz Interface - Interactive quiz taking experience."""

import time
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

console = Console()


class QuizInterface:
    """Interactive quiz interface for the CLI."""

    def __init__(self) -> None:
        self.current_question = 0
        self.answers: Dict[str, str] = {}
        self.start_time: Optional[float] = None
        self.question_times: List[float] = []

    def display_header(self, topic: str, total_questions: int) -> None:
        """Display quiz header."""
        console.print(Panel.fit(
            f"[bold blue]Quiz: {topic}[/bold blue]\n"
            f"Questions: {total_questions}",
            border_style="blue",
        ))
        console.print("[dim]Type 'quit' to exit early, 'skip' to skip a question.[/dim]\n")

    def display_question(
        self,
        question_num: int,
        total: int,
        question_text: str,
        question_type: str,
        options: Optional[List[str]] = None,
        topic: Optional[str] = None,
    ) -> None:
        """Display a quiz question."""
        # Header
        header = f"Question {question_num}/{total}"
        if topic:
            header += f" | [dim]{topic}[/dim]"

        console.print()
        console.print(Panel(
            f"[bold]{question_text}[/bold]",
            title=f"[bold blue]{header}[/bold blue]",
            border_style="blue",
            padding=(1, 2),
        ))

        # Display options for multiple choice
        if question_type == "multiple_choice" and options:
            letters = ["A", "B", "C", "D", "E", "F"]
            console.print()
            for i, option in enumerate(options):
                if i < len(letters):
                    console.print(f"  [cyan][{letters[i]}][/cyan] {option}")

    def get_answer(
        self,
        question_type: str,
        options: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], bool]:
        """Get user's answer.

        Returns:
            Tuple of (answer, should_quit)
        """
        if question_type == "multiple_choice" and options:
            valid_answers = ["a", "b", "c", "d", "e", "f"][:len(options)]
            valid_answers.extend(["quit", "skip", "q", "s"])

            while True:
                answer = Prompt.ask("\n[bold]Your answer[/bold]").strip().lower()

                if answer in ["quit", "q"]:
                    return None, True
                if answer in ["skip", "s"]:
                    return "skip", False
                if answer in valid_answers[:len(options)]:
                    return answer.upper(), False

                console.print(f"[red]Please enter {', '.join(valid_answers[:len(options)])}[/red]")

        else:
            # Short answer or open-ended
            answer = Prompt.ask("\n[bold]Your answer[/bold]").strip()

            if answer.lower() in ["quit", "q"]:
                return None, True
            if answer.lower() in ["skip", "s"]:
                return "skip", False

            return answer, False

    def display_answer_feedback(
        self,
        is_correct: bool,
        correct_answer: Optional[str] = None,
        explanation: Optional[str] = None,
    ) -> None:
        """Display feedback for an answer."""
        if is_correct:
            console.print("\n[green]Correct![/green]")
        else:
            console.print("\n[red]Incorrect[/red]")
            if correct_answer:
                console.print(f"[dim]Correct answer: {correct_answer}[/dim]")

        if explanation:
            console.print(f"\n[italic dim]{explanation}[/italic dim]")

    def display_results(
        self,
        correct: int,
        total: int,
        time_taken: float,
        question_results: Optional[List[dict]] = None,
    ) -> None:
        """Display quiz results."""
        score = correct / total if total > 0 else 0

        # Determine color based on score
        if score >= 0.8:
            color = "green"
            emoji = ""
        elif score >= 0.6:
            color = "yellow"
            emoji = ""
        else:
            color = "red"
            emoji = ""

        console.print("\n")
        console.print(Panel.fit(
            f"[bold {color}]{emoji} Quiz Complete![/bold {color}]",
            border_style=color,
        ))

        # Summary table
        table = Table(show_header=False, box=None)
        table.add_column("Stat", style="bold")
        table.add_column("Value")

        table.add_row("Score", f"[{color}]{correct}/{total} ({score:.0%})[/{color}]")
        table.add_row("Time", f"{time_taken:.0f} seconds")
        table.add_row("Avg per question", f"{time_taken/total:.1f}s" if total > 0 else "N/A")

        console.print(table)

        # Detailed results if available
        if question_results:
            console.print("\n[bold]Question Breakdown:[/bold]")

            for i, result in enumerate(question_results, 1):
                status = "[green]Correct[/green]" if result.get("correct") else "[red]Wrong[/red]"
                console.print(f"  Q{i}: {status}")

                if not result.get("correct") and result.get("topic"):
                    console.print(f"       [dim]Review: {result['topic']}[/dim]")


def run_quiz(
    questions: List[dict],
    topic: str = "General",
) -> dict:
    """Run an interactive quiz session.

    Args:
        questions: List of question dicts with:
            - id: Question ID
            - question_text: The question
            - question_type: "multiple_choice" or "short_answer"
            - options: List of options (for multiple choice)
            - correct_answer: The correct answer
            - explanation: Optional explanation
            - topic: Optional topic name
        topic: Overall quiz topic

    Returns:
        Dict with:
            - score: Float (0-1)
            - correct: Number correct
            - total: Total questions
            - time_seconds: Time taken
            - answers: Dict of question_id -> user_answer
            - results: List of per-question results
    """
    interface = QuizInterface()
    interface.display_header(topic, len(questions))

    start_time = time.time()
    answers: Dict[str, str] = {}
    results: List[dict] = []
    correct_count = 0

    for i, question in enumerate(questions, 1):
        question_start = time.time()

        interface.display_question(
            question_num=i,
            total=len(questions),
            question_text=question["question_text"],
            question_type=question.get("question_type", "short_answer"),
            options=question.get("options"),
            topic=question.get("topic"),
        )

        answer, should_quit = interface.get_answer(
            question_type=question.get("question_type", "short_answer"),
            options=question.get("options"),
        )

        if should_quit:
            console.print("\n[yellow]Quiz ended early.[/yellow]")
            break

        question_time = time.time() - question_start

        if answer == "skip":
            answers[question["id"]] = ""
            results.append({
                "question_id": question["id"],
                "correct": False,
                "skipped": True,
                "topic": question.get("topic"),
                "time": question_time,
            })
            console.print("[dim]Skipped[/dim]")
            continue

        # Check answer
        answers[question["id"]] = answer
        correct_answer = question.get("correct_answer", "")

        # Simple string comparison (could be enhanced with fuzzy matching)
        is_correct = answer.lower().strip() == str(correct_answer).lower().strip()

        if is_correct:
            correct_count += 1

        interface.display_answer_feedback(
            is_correct=is_correct,
            correct_answer=correct_answer if not is_correct else None,
            explanation=question.get("explanation"),
        )

        results.append({
            "question_id": question["id"],
            "correct": is_correct,
            "skipped": False,
            "user_answer": answer,
            "correct_answer": correct_answer,
            "topic": question.get("topic"),
            "time": question_time,
        })

    total_time = time.time() - start_time
    total_answered = len(results)

    interface.display_results(
        correct=correct_count,
        total=total_answered,
        time_taken=total_time,
        question_results=results,
    )

    return {
        "score": correct_count / total_answered if total_answered > 0 else 0,
        "correct": correct_count,
        "total": total_answered,
        "time_seconds": total_time,
        "answers": answers,
        "results": results,
    }
