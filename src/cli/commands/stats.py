"""Stats Commands - Progress, streak, and topic mastery."""

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.cli.state import get_current_user_id, require_auth
from src.cli.ui.display import display_streak_info

stats_app = typer.Typer(help="Progress and statistics commands")
console = Console()


def run_async(coro):
    """Helper to run async functions in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@stats_app.command("progress")
def progress() -> None:
    """View your overall learning progress."""
    require_auth()
    user_id = get_current_user_id()

    console.print(Panel.fit(
        "[bold cyan]Learning Progress[/bold cyan]",
        border_style="cyan",
    ))

    try:
        from src.modules.session import get_session_service
        from src.modules.adaptation import get_adaptation_service

        session_service = get_session_service()
        adaptation_service = get_adaptation_service()

        # Get streak info
        streak_info = run_async(session_service.get_streak_info(user_id))

        # Display streak
        current = streak_info.get("current_streak", 0)
        longest = streak_info.get("longest_streak", 0)

        if current > 0:
            fire = "" * min(current, 7)
            console.print(f"\n{fire} [bold]{current}[/bold] day streak")
        else:
            console.print("\n[dim]No active streak[/dim]")

        console.print(f"Best streak: {longest} days")

        if streak_info.get("streak_at_risk"):
            console.print("[yellow]Your streak is at risk! Study today.[/yellow]")

        # Get learning patterns
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as prog:
            prog.add_task(description="Analyzing patterns...", total=None)
            patterns = run_async(adaptation_service.analyze_patterns(user_id))

        # Performance section
        console.print("\n[bold]Performance:[/bold]")

        perf = patterns.get("performance", {})
        quiz_avg = perf.get("quiz_score_avg", 0)
        quiz_trend = perf.get("quiz_score_trend", "stable")
        feynman_avg = perf.get("feynman_score_avg", 0)
        feynman_trend = perf.get("feynman_score_trend", "stable")

        trend_icons = {"improving": "", "declining": "", "stable": ""}

        console.print(f"  Quiz average: {quiz_avg:.0%} {trend_icons.get(quiz_trend, '')}")
        console.print(f"  Feynman average: {feynman_avg:.0%} {trend_icons.get(feynman_trend, '')}")

        # Engagement section
        console.print("\n[bold]Engagement:[/bold]")

        eng = patterns.get("engagement", {})
        console.print(f"  Sessions (7 days): {eng.get('sessions_last_7_days', 0)}")
        console.print(f"  Sessions (30 days): {eng.get('sessions_last_30_days', 0)}")
        console.print(f"  Avg duration: {eng.get('avg_session_duration', 0)} min")
        console.print(f"  Completion rate: {eng.get('completion_rate', 0):.0%}")

        # Current settings
        console.print("\n[bold]Current Settings:[/bold]")

        settings = patterns.get("current_settings", {})
        console.print(f"  Pace: {settings.get('pace', 'normal')}")
        console.print(f"  Difficulty: {settings.get('difficulty_level', 3)}/5")

        # Recommendations
        try:
            pace_rec = run_async(adaptation_service.get_pace_recommendation(user_id))
            if pace_rec.recommended_pace != pace_rec.current_pace:
                console.print(f"\n[yellow]Recommendation:[/yellow]")
                console.print(f"  Consider pace: '{pace_rec.recommended_pace}'")
                console.print(f"  [dim]{pace_rec.reason}[/dim]")
        except Exception:
            pass

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@stats_app.command("streak")
def streak() -> None:
    """View your streak status and history."""
    require_auth()
    user_id = get_current_user_id()

    try:
        from src.modules.session import get_session_service

        service = get_session_service()
        streak_info = run_async(service.get_streak_info(user_id))

        display_streak_info(streak_info)

        # Weekly activity
        console.print("\n[bold]This Week:[/bold]")

        # Get recent sessions for activity display
        sessions = run_async(service.get_session_history(
            user_id=user_id,
            limit=7,
            include_abandoned=False,
        ))

        # Create week visualization
        from datetime import datetime, timedelta

        today = datetime.utcnow().date()
        week_start = today - timedelta(days=today.weekday())

        week_activity = {}
        for session in sessions:
            session_date = session.started_at.date()
            if week_start <= session_date <= today:
                week_activity[session_date] = True

        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        activity_str = ""
        for i, day in enumerate(days):
            check_date = week_start + timedelta(days=i)
            if check_date > today:
                activity_str += f"[dim]{day}: -[/dim]  "
            elif check_date in week_activity:
                activity_str += f"[green]{day}:[/green]  "
            else:
                activity_str += f"[red]{day}:[/red]  "

        console.print(f"  {activity_str}")

        # Tips based on streak
        current = streak_info.get("current_streak", 0)
        if current == 0:
            console.print("\n[dim]Tip: Start a session today to begin your streak![/dim]")
        elif current < 7:
            console.print(f"\n[dim]Tip: {7 - current} more days to your first week![/dim]")
        elif current >= 7 and current < 30:
            console.print(f"\n[dim]Tip: {30 - current} more days to a month streak![/dim]")
        else:
            console.print("\n[green]Amazing! Keep up the great work![/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@stats_app.command("topics")
def topics() -> None:
    """View topic mastery levels."""
    require_auth()
    user_id = get_current_user_id()

    console.print(Panel.fit(
        "[bold]Topic Mastery[/bold]",
        border_style="cyan",
    ))

    try:
        from src.modules.assessment import get_assessment_service

        service = get_assessment_service()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as prog:
            prog.add_task(description="Loading topic data...", total=None)
            topic_progress = run_async(service.get_topic_progress(user_id))

        if not topic_progress:
            console.print("\n[dim]No topic data yet. Complete some quizzes to see progress.[/dim]")
            return

        # Sort by mastery level
        sorted_topics = sorted(
            topic_progress.items(),
            key=lambda x: x[1].get("mastery_level", 0),
            reverse=True,
        )

        console.print()

        for topic_name, data in sorted_topics:
            mastery = data.get("mastery_level", 0)
            quiz_count = data.get("quiz_count", 0)
            last_quiz = data.get("last_quiz_date")

            # Create progress bar
            bar_width = 20
            filled = int(mastery * bar_width)
            bar = "" * filled + "" * (bar_width - filled)

            # Color based on mastery
            if mastery >= 0.8:
                color = "green"
            elif mastery >= 0.5:
                color = "yellow"
            else:
                color = "red"

            console.print(f"[bold]{topic_name}[/bold]")
            console.print(f"  [{color}][{bar}] {mastery:.0%}[/{color}]")
            console.print(f"  [dim]Quizzes: {quiz_count} | Last: {last_quiz or 'Never'}[/dim]")
            console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@stats_app.command("gaps")
def gaps() -> None:
    """View identified knowledge gaps."""
    require_auth()
    user_id = get_current_user_id()

    console.print(Panel.fit(
        "[bold yellow]Knowledge Gaps[/bold yellow]",
        border_style="yellow",
    ))

    try:
        from src.modules.assessment import get_assessment_service

        service = get_assessment_service()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as prog:
            prog.add_task(description="Analyzing gaps...", total=None)
            gaps = run_async(service.get_knowledge_gaps(user_id))

        if not gaps:
            console.print("\n[green]No knowledge gaps identified![/green]")
            console.print("[dim]Keep practicing to maintain your understanding.[/dim]")
            return

        console.print(f"\n[yellow]{len(gaps)} areas need attention:[/yellow]\n")

        for i, gap in enumerate(gaps, 1):
            topic = gap.get("topic", "Unknown")
            severity = gap.get("severity", "medium")
            last_attempt = gap.get("last_attempt")
            suggested_action = gap.get("suggested_action", "Review this topic")

            severity_colors = {"high": "red", "medium": "yellow", "low": "cyan"}
            color = severity_colors.get(severity, "white")

            console.print(f"[bold]{i}. {topic}[/bold]")
            console.print(f"   Severity: [{color}]{severity.upper()}[/{color}]")
            console.print(f"   [dim]Last attempt: {last_attempt or 'Unknown'}[/dim]")
            console.print(f"   [italic]{suggested_action}[/italic]")
            console.print()

        console.print("[dim]Tip: Use 'learner learn start --type drill' to focus on weak areas.[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@stats_app.command("reviews")
def reviews() -> None:
    """View items due for spaced repetition review."""
    require_auth()
    user_id = get_current_user_id()

    console.print(Panel.fit(
        "[bold]Spaced Repetition Reviews[/bold]",
        border_style="cyan",
    ))

    try:
        from src.modules.assessment import get_assessment_service

        service = get_assessment_service()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as prog:
            prog.add_task(description="Checking review schedule...", total=None)
            due_items = run_async(service.get_due_reviews(user_id))

        if not due_items:
            console.print("\n[green]No reviews due![/green]")
            console.print("[dim]You're all caught up.[/dim]")
            return

        # Group by urgency
        overdue = [item for item in due_items if item.get("overdue", False)]
        due_today = [item for item in due_items if not item.get("overdue") and item.get("due_today")]
        upcoming = [item for item in due_items if not item.get("overdue") and not item.get("due_today")]

        if overdue:
            console.print(f"\n[red]Overdue ({len(overdue)}):[/red]")
            for item in overdue[:5]:
                console.print(f"  - {item.get('topic', 'Unknown')}")

        if due_today:
            console.print(f"\n[yellow]Due Today ({len(due_today)}):[/yellow]")
            for item in due_today[:5]:
                console.print(f"  - {item.get('topic', 'Unknown')}")

        if upcoming:
            console.print(f"\n[dim]Coming Up ({len(upcoming)}):[/dim]")
            for item in upcoming[:3]:
                console.print(f"  - {item.get('topic', 'Unknown')}: {item.get('due_date', 'Soon')}")

        total = len(overdue) + len(due_today)
        if total > 0:
            console.print(f"\n[dim]Start a session to review these {total} items.[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@stats_app.command("summary")
def summary(
    days: int = typer.Option(7, "--days", "-d", help="Number of days to summarize"),
) -> None:
    """View a summary of recent learning activity."""
    require_auth()
    user_id = get_current_user_id()

    console.print(Panel.fit(
        f"[bold]Last {days} Days Summary[/bold]",
        border_style="cyan",
    ))

    try:
        from src.modules.session import get_session_service

        service = get_session_service()

        # Get recent sessions
        sessions = run_async(service.get_session_history(
            user_id=user_id,
            limit=50,  # Get more to filter
            include_abandoned=True,
        ))

        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)

        recent = [s for s in sessions if s.started_at >= cutoff]
        completed = [s for s in recent if s.status.value == "completed"]
        abandoned = [s for s in recent if s.status.value == "abandoned"]

        # Calculate stats
        total_time = sum(
            (s.actual_duration_minutes or s.planned_duration_minutes)
            for s in completed
        )

        table = Table(show_header=False, box=None)
        table.add_column("Stat", style="bold")
        table.add_column("Value")

        table.add_row("Sessions Completed", str(len(completed)))
        table.add_row("Sessions Abandoned", str(len(abandoned)))
        table.add_row("Total Learning Time", f"{total_time} minutes ({total_time // 60}h {total_time % 60}m)")
        if completed:
            table.add_row("Avg Session Length", f"{total_time // len(completed)} minutes")

        console.print()
        console.print(table)

        # Session types breakdown
        if completed:
            console.print("\n[bold]Session Types:[/bold]")
            type_counts = {}
            for s in completed:
                stype = s.session_type.value
                type_counts[stype] = type_counts.get(stype, 0) + 1

            for stype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
                console.print(f"  {stype.title()}: {count}")

        # Daily breakdown
        console.print("\n[bold]Daily Activity:[/bold]")
        daily = {}
        for s in completed:
            day = s.started_at.strftime("%a %m/%d")
            if day not in daily:
                daily[day] = 0
            daily[day] += s.actual_duration_minutes or s.planned_duration_minutes

        for day, minutes in daily.items():
            bar = "" * (minutes // 10)  # 1 block = 10 minutes
            console.print(f"  {day}: [{bar}] {minutes}m")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
