"""Display Utilities - Rich output formatting."""

from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.table import Table

console = Console()


def display_session_plan(plan) -> None:
    """Display a session plan in a formatted table."""
    console.print(Panel.fit(
        f"[bold cyan]Session Plan[/bold cyan]\n"
        f"Duration: {plan.total_duration_minutes} minutes",
        border_style="cyan",
    ))

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Activity", min_width=15)
    table.add_column("Duration", width=10)
    table.add_column("Description", min_width=30)

    for item in plan.items:
        activity_name = item.activity_type.value.replace("_", " ").title()

        # Add icons for different activity types
        icons = {
            "content_consumption": "[blue]>>[/blue]",
            "quiz": "[green]?[/green]",
            "feynman_explanation": "[magenta]![/magenta]",
            "review": "[yellow]*[/yellow]",
        }
        icon = icons.get(item.activity_type.value, " ")

        table.add_row(
            str(item.order + 1),
            f"{icon} {activity_name}",
            f"{item.duration_minutes} min",
            item.description[:40] + "..." if len(item.description) > 40 else item.description,
        )

    console.print(table)

    # Summary
    console.print(f"\n[dim]Consumption: {plan.consumption_minutes} min | "
                  f"Production: {plan.production_minutes} min[/dim]")

    if plan.includes_review:
        console.print("[yellow]Includes spaced repetition review items[/yellow]")


def display_session_summary(summary) -> None:
    """Display session summary in a nice format."""
    console.print("\n")
    console.print(Panel.fit(
        "[bold green]Session Complete![/bold green]",
        border_style="green",
    ))

    # Stats table
    table = Table(show_header=False, box=None)
    table.add_column("Stat", style="bold")
    table.add_column("Value")

    table.add_row("Duration", f"{summary.duration_minutes} minutes")
    table.add_row("Activities", str(summary.activities_completed))
    table.add_row("Content Items", str(summary.content_consumed))

    if summary.quiz_score is not None:
        score_color = "green" if summary.quiz_score >= 0.7 else "yellow" if summary.quiz_score >= 0.5 else "red"
        table.add_row("Quiz Score", f"[{score_color}]{summary.quiz_score:.0%}[/{score_color}]")

    if summary.feynman_score is not None:
        score_color = "green" if summary.feynman_score >= 0.7 else "yellow"
        table.add_row("Feynman Score", f"[{score_color}]{summary.feynman_score:.0%}[/{score_color}]")

    console.print(table)

    # Topics covered
    if summary.topics_covered:
        console.print(f"\n[bold]Topics:[/bold] {', '.join(summary.topics_covered)}")

    # Streak
    if summary.streak_updated:
        console.print("\n[green]Streak updated![/green]")

    # Knowledge gaps
    if summary.new_gaps_identified:
        console.print("\n[yellow]Areas to review:[/yellow]")
        for gap in summary.new_gaps_identified:
            console.print(f"  - {gap}")

    # Next session preview
    if summary.next_session_preview:
        console.print(f"\n[dim]Next time: {summary.next_session_preview}[/dim]")


def display_content_card(content, index: Optional[int] = None) -> None:
    """Display a content item as a card."""
    prefix = f"{index}. " if index else ""

    # Determine difficulty color
    diff_colors = {1: "green", 2: "green", 3: "yellow", 4: "red", 5: "red"}
    diff_color = diff_colors.get(content.difficulty_level, "white")

    console.print(f"\n[bold cyan]{prefix}{content.title}[/bold cyan]")
    console.print(f"  [dim]Source:[/dim] {content.source_type.value.upper()}")
    console.print(f"  [dim]Relevance:[/dim] {content.relevance_score:.0%} | "
                  f"[{diff_color}]Difficulty: {content.difficulty_level}/5[/{diff_color}]")

    if content.summary:
        summary = content.summary[:150] + "..." if len(content.summary) > 150 else content.summary
        console.print(f"  {summary}")

    if content.source_url:
        console.print(f"  [dim]{content.source_url}[/dim]")


def display_progress_bar(
    label: str,
    progress: float,
    width: int = 20,
    filled_char: str = "",
    empty_char: str = "",
) -> str:
    """Create a text-based progress bar."""
    filled = int(progress * width)
    empty = width - filled

    bar = filled_char * filled + empty_char * empty
    percentage = f"{progress:.0%}"

    return f"{label}: [{bar}] {percentage}"


def display_streak_info(streak_info: dict) -> None:
    """Display streak information."""
    console.print(Panel.fit(
        "[bold]Streak Status[/bold]",
        border_style="cyan",
    ))

    current = streak_info.get("current_streak", 0)
    longest = streak_info.get("longest_streak", 0)
    at_risk = streak_info.get("streak_at_risk", False)

    # Streak visual
    if current > 0:
        fire = "" * min(current, 7)  # Max 7 flames for display
        console.print(f"  {fire} [bold]{current}[/bold] day{'s' if current != 1 else ''}")
    else:
        console.print("  [dim]No active streak[/dim]")

    console.print(f"  Best: {longest} days")

    if at_risk:
        console.print("  [yellow]Your streak is at risk! Study today to keep it going.[/yellow]")

    last_date = streak_info.get("last_session_date")
    if last_date:
        console.print(f"  [dim]Last session: {last_date}[/dim]")


def display_quiz_question(
    question_num: int,
    total: int,
    question_text: str,
    options: Optional[List[str]] = None,
    topic: Optional[str] = None,
) -> None:
    """Display a quiz question."""
    header = f"Question {question_num}/{total}"
    if topic:
        header += f" - {topic}"

    console.print(Panel(
        f"[bold]{question_text}[/bold]",
        title=f"[bold blue]{header}[/bold blue]",
        border_style="blue",
    ))

    if options:
        letters = ["A", "B", "C", "D", "E", "F"]
        for i, option in enumerate(options):
            console.print(f"  [{letters[i]}] {option}")
        console.print()


def display_quiz_result(
    is_correct: bool,
    correct_answer: Optional[str] = None,
    explanation: Optional[str] = None,
) -> None:
    """Display quiz answer feedback."""
    if is_correct:
        console.print("[green]Correct![/green]")
    else:
        console.print("[red]Incorrect[/red]")
        if correct_answer:
            console.print(f"[dim]The correct answer was: {correct_answer}[/dim]")

    if explanation:
        console.print(f"\n[dim]{explanation}[/dim]")


def display_feynman_dialogue(
    agent_message: str,
    turn: int,
    gaps: Optional[List[str]] = None,
) -> None:
    """Display Socratic agent dialogue in Feynman exercise."""
    console.print(Panel(
        agent_message,
        title=f"[bold magenta]Socratic Guide (Turn {turn})[/bold magenta]",
        border_style="magenta",
    ))

    if gaps:
        console.print("\n[yellow]Identified gaps so far:[/yellow]")
        for gap in gaps:
            console.print(f"  - {gap}")


def display_feynman_evaluation(evaluation: dict) -> None:
    """Display Feynman explanation evaluation."""
    console.print(Panel.fit(
        "[bold green]Explanation Evaluation[/bold green]",
        border_style="green",
    ))

    scores = [
        ("Completeness", evaluation.get("completeness_score", 0)),
        ("Accuracy", evaluation.get("accuracy_score", 0)),
        ("Simplicity", evaluation.get("simplicity_score", 0)),
        ("Overall", evaluation.get("overall_score", 0)),
    ]

    for label, score in scores:
        bar = display_progress_bar(label, score)
        console.print(f"  {bar}")

    if evaluation.get("feedback"):
        console.print(f"\n[dim]{evaluation['feedback']}[/dim]")

    if evaluation.get("gaps_identified"):
        console.print("\n[yellow]Areas for improvement:[/yellow]")
        for gap in evaluation["gaps_identified"]:
            console.print(f"  - {gap}")
