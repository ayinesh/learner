"""Learning Session Commands - Start, status, end sessions."""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from src.cli.state import get_current_user_id, require_auth
from src.cli.ui.display import display_session_plan, display_session_summary
from src.shared.models import SessionType

learn_app = typer.Typer(help="Learning session commands")
console = Console()


def run_async(coro):
    """Helper to run async functions in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@learn_app.command("start")
def start(
    minutes: int = typer.Option(
        None,
        "--time",
        "-t",
        help="Available time in minutes (10-180)",
    ),
    session_type: str = typer.Option(
        "regular",
        "--type",
        help="Session type: regular, drill, or catchup",
    ),
) -> None:
    """Start a new learning session."""
    require_auth()
    user_id = get_current_user_id()

    # Check for existing active session
    try:
        from src.modules.session import get_session_service

        service = get_session_service()
        active = run_async(service.get_current_session(user_id))

        if active:
            console.print("[yellow]You have an active session.[/yellow]")
            console.print(f"Session ID: [dim]{active.id}[/dim]")
            console.print(f"Started: {active.started_at.strftime('%H:%M')}")

            if Confirm.ask("End the current session first?"):
                summary = run_async(service.end_session(active.id))
                display_session_summary(summary)
                console.print()
            else:
                console.print("[dim]Use 'learner learn status' to see current session.[/dim]")
                raise typer.Exit(0)

    except Exception as e:
        console.print(f"[red]Error checking active session:[/red] {e}")

    # Determine session type
    try:
        stype = SessionType(session_type.lower())
    except ValueError:
        console.print(f"[red]Invalid session type: {session_type}[/red]")
        console.print("Valid types: regular, drill, catchup")
        raise typer.Exit(1)

    # Get time if not specified
    if minutes is None:
        from src.modules.user import get_user_service

        user_service = get_user_service()
        profile = run_async(user_service.get_profile(user_id))

        default_time = profile.time_budget_minutes if profile else 30
        minutes = IntPrompt.ask(
            "How many minutes do you have?",
            default=default_time,
        )

    # Validate time
    if minutes < 10:
        console.print("[yellow]Minimum session is 10 minutes. Setting to 10.[/yellow]")
        minutes = 10
    elif minutes > 180:
        console.print("[yellow]Maximum session is 180 minutes. Setting to 180.[/yellow]")
        minutes = 180

    # Load learning context to show restoration info
    from src.modules.session.restoration_service import get_restoration_service

    restoration_service = get_restoration_service()
    welcome_ctx = run_async(restoration_service.get_welcome_context(user_id))

    # Display session info with context restoration
    type_emoji = {
        SessionType.REGULAR: "",
        SessionType.DRILL: "",
        SessionType.CATCHUP: "",
    }

    # Build session info panel
    session_info_lines = [
        f"[bold green]{type_emoji.get(stype, '')} Starting {stype.value.title()} Session[/bold green]",
        f"Duration: {minutes} minutes",
    ]

    # Show restored context if available
    if welcome_ctx.primary_goal:
        session_info_lines.append("")
        session_info_lines.append(f"[cyan]Goal:[/cyan] {welcome_ctx.primary_goal}")
        if welcome_ctx.current_focus:
            session_info_lines.append(f"[cyan]Focus:[/cyan] {welcome_ctx.current_focus}")
        if welcome_ctx.learning_progress > 0:
            progress_pct = int(welcome_ctx.learning_progress * 100)
            session_info_lines.append(f"[cyan]Progress:[/cyan] {progress_pct}%")

    if welcome_ctx.current_streak > 0:
        streak_text = f"[cyan]Streak:[/cyan] {welcome_ctx.current_streak} days"
        if welcome_ctx.streak_at_risk:
            streak_text += " [yellow](keep it going!)[/yellow]"
        session_info_lines.append(streak_text)

    console.print(Panel.fit(
        "\n".join(session_info_lines),
        border_style="green",
    ))

    try:
        from src.modules.session import get_session_service

        service = get_session_service()

        # Start session
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Creating session...", total=None)
            session = run_async(service.start_session(
                user_id=user_id,
                available_minutes=minutes,
                session_type=stype,
            ))

        console.print(f"\n[green]Session started![/green] ID: [dim]{session.id}[/dim]")

        # Get and display plan
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Planning session...", total=None)
            plan = run_async(service.get_session_plan(session.id))

        console.print()
        display_session_plan(plan)

        # Get coach greeting
        try:
            from src.modules.agents import get_orchestrator

            orchestrator = get_orchestrator()

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description="Preparing...", total=None)
                response = run_async(orchestrator.route_message(
                    user_id=user_id,
                    message="I'm starting a learning session",
                    session_id=session.id,
                ))

            console.print(Panel(
                response.message,
                title="[bold cyan]Coach[/bold cyan]",
                border_style="cyan",
            ))

        except Exception as e:
            console.print(f"[dim]Coach unavailable: {e}[/dim]")

        console.print("\n[dim]Type your responses or 'quit' to end the session.[/dim]")

        # Interactive loop
        _run_session_loop(service, session.id, user_id)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def _run_session_loop(service, session_id, user_id) -> None:
    """Run the interactive session loop."""
    from src.modules.agents import get_orchestrator

    orchestrator = get_orchestrator()

    while True:
        try:
            user_input = Prompt.ask("\n[bold]You[/bold]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Session interrupted.[/yellow]")
            break

        # Check for commands
        if user_input.lower() in ("quit", "exit", "q"):
            if Confirm.ask("End this session?"):
                summary = run_async(service.end_session(session_id))
                display_session_summary(summary)
                break
            continue

        if user_input.lower() == "status":
            session = run_async(service.get_current_session(user_id))
            if session:
                from datetime import datetime
                elapsed = (datetime.utcnow() - session.started_at).seconds // 60
                console.print(f"[dim]Session active: {elapsed} minutes elapsed[/dim]")
            continue

        if user_input.lower() == "plan":
            plan = run_async(service.get_session_plan(session_id))
            display_session_plan(plan)
            continue

        if user_input.lower() == "quiz":
            _start_quick_quiz(user_id, session_id)
            continue

        if user_input.lower().startswith("explain "):
            topic = user_input[8:].strip()
            _start_feynman(user_id, topic, session_id)
            continue

        if user_input.lower() == "help":
            _show_session_help()
            continue

        # Route to AI
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Thinking...", total=None)
            try:
                response = run_async(orchestrator.route_message(
                    user_id=user_id,
                    message=user_input,
                    session_id=session_id,
                ))
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")
                continue

        agent_name = response.agent_type.value.replace("_", " ").title()
        console.print(Panel(
            response.message,
            title=f"[bold cyan]{agent_name}[/bold cyan]",
            border_style="cyan",
        ))

        if response.end_conversation:
            if Confirm.ask("The agent suggests ending. End session?"):
                summary = run_async(service.end_session(session_id))
                display_session_summary(summary)
                break


def _show_session_help() -> None:
    """Show session help."""
    console.print(Panel(
        "[bold]Session Commands:[/bold]\n\n"
        "  [cyan]quit[/cyan]        - End the session\n"
        "  [cyan]status[/cyan]      - Show session status\n"
        "  [cyan]plan[/cyan]        - View session plan\n"
        "  [cyan]quiz[/cyan]        - Start a quick quiz\n"
        "  [cyan]explain <topic>[/cyan] - Start Feynman dialogue\n"
        "  [cyan]help[/cyan]        - Show this help\n\n"
        "[dim]Or just type naturally to interact with the AI agents.[/dim]",
        title="[bold]Help[/bold]",
        border_style="cyan",
    ))


def _start_quick_quiz(user_id, session_id) -> None:
    """Start a quick quiz during session."""
    console.print("\n[blue]Starting quick quiz...[/blue]")

    try:
        from src.modules.agents import get_orchestrator

        orchestrator = get_orchestrator()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Generating quiz...", total=None)
            response = run_async(orchestrator.start_quiz(
                user_id=user_id,
                topics=["recent"],  # Quiz on recent topics
                question_count=3,
            ))

        console.print(Panel(
            response.message,
            title="[bold blue]Assessment[/bold blue]",
            border_style="blue",
        ))

    except Exception as e:
        console.print(f"[red]Error starting quiz:[/red] {e}")


def _start_feynman(user_id, topic: str, session_id) -> None:
    """Start a Feynman dialogue during session."""
    console.print(f"\n[magenta]Starting Feynman dialogue on: {topic}[/magenta]")

    try:
        from src.modules.agents import get_orchestrator

        orchestrator = get_orchestrator()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Preparing dialogue...", total=None)
            response = run_async(orchestrator.start_feynman_dialogue(
                user_id=user_id,
                topic=topic,
            ))

        console.print(Panel(
            response.message,
            title="[bold magenta]Socratic Guide[/bold magenta]",
            border_style="magenta",
        ))

    except Exception as e:
        console.print(f"[red]Error starting dialogue:[/red] {e}")


@learn_app.command("status")
def status() -> None:
    """Check current session status."""
    require_auth()
    user_id = get_current_user_id()

    try:
        from src.modules.session import get_session_service

        service = get_session_service()
        session = run_async(service.get_current_session(user_id))

        if not session:
            console.print("[dim]No active session.[/dim]")
            console.print("Start one with 'learner learn start'")
            return

        # Calculate elapsed time
        from datetime import datetime
        elapsed = (datetime.utcnow() - session.started_at).seconds // 60
        remaining = max(0, session.planned_duration_minutes - elapsed)

        console.print(Panel.fit(
            f"[bold green]Active Session[/bold green]",
            border_style="green",
        ))

        table = Table(show_header=False, box=None)
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Session ID", f"[dim]{session.id}[/dim]")
        table.add_row("Type", session.session_type.value.title())
        table.add_row("Status", session.status.value.title())
        table.add_row("Started", session.started_at.strftime("%H:%M"))
        table.add_row("Elapsed", f"{elapsed} minutes")
        table.add_row("Remaining", f"~{remaining} minutes")

        console.print(table)

        # Get activities
        activities = run_async(service.get_session_activities(session.id))
        if activities:
            console.print(f"\n[bold]Activities:[/bold] {len(activities)} completed")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@learn_app.command("end")
def end() -> None:
    """End the current learning session."""
    require_auth()
    user_id = get_current_user_id()

    try:
        from src.modules.session import get_session_service

        service = get_session_service()
        session = run_async(service.get_current_session(user_id))

        if not session:
            console.print("[dim]No active session to end.[/dim]")
            return

        if not Confirm.ask(f"End session {str(session.id)[:8]}...?"):
            console.print("[dim]Cancelled.[/dim]")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Ending session...", total=None)
            summary = run_async(service.end_session(session.id))

        display_session_summary(summary)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@learn_app.command("abandon")
def abandon(
    reason: str = typer.Option(None, "--reason", "-r", help="Reason for abandoning"),
) -> None:
    """Abandon the current session without completing."""
    require_auth()
    user_id = get_current_user_id()

    try:
        from src.modules.session import get_session_service

        service = get_session_service()
        session = run_async(service.get_current_session(user_id))

        if not session:
            console.print("[dim]No active session.[/dim]")
            return

        if not Confirm.ask("[yellow]Abandon this session? (Won't count toward streak)[/yellow]"):
            console.print("[dim]Cancelled.[/dim]")
            return

        run_async(service.abandon_session(session.id, reason))
        console.print("[yellow]Session abandoned.[/yellow]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@learn_app.command("history")
def history(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of sessions"),
    include_abandoned: bool = typer.Option(False, "--all", "-a", help="Include abandoned"),
) -> None:
    """View session history."""
    require_auth()
    user_id = get_current_user_id()

    try:
        from src.modules.session import get_session_service

        service = get_session_service()
        sessions = run_async(service.get_session_history(
            user_id=user_id,
            limit=limit,
            include_abandoned=include_abandoned,
        ))

        if not sessions:
            console.print("[dim]No session history.[/dim]")
            console.print("Start your first session with 'learner learn start'")
            return

        console.print(Panel.fit(
            "[bold]Session History[/bold]",
            border_style="cyan",
        ))

        table = Table(show_header=True, header_style="bold")
        table.add_column("Date", style="dim")
        table.add_column("Type")
        table.add_column("Status")
        table.add_column("Duration")

        for session in sessions:
            status_colors = {
                "completed": "green",
                "in_progress": "yellow",
                "abandoned": "red",
            }
            status_color = status_colors.get(session.status.value, "white")

            duration = session.actual_duration_minutes or session.planned_duration_minutes

            table.add_row(
                session.started_at.strftime("%Y-%m-%d %H:%M"),
                session.session_type.value.title(),
                f"[{status_color}]{session.status.value}[/{status_color}]",
                f"{duration} min",
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
