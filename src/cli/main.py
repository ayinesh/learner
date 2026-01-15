"""CLI Entry Point - Main command interface.

This module provides the main entry point for the Learner CLI application.
It sets up command groups and provides quick access commands for common operations.
"""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt

# Main application
app = typer.Typer(
    name="learner",
    help="Learner - Your AI-powered personalized learning companion",
    no_args_is_help=True,
    pretty_exceptions_enable=True,
)
console = Console()


import atexit

# Global event loop for CLI - reuse across commands
_cli_loop = None

def _get_cli_loop():
    """Get or create the CLI event loop."""
    global _cli_loop
    if _cli_loop is None or _cli_loop.is_closed():
        _cli_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_cli_loop)
    return _cli_loop

def _cleanup_loop():
    """Cleanup function called at exit."""
    global _cli_loop
    if _cli_loop is not None and not _cli_loop.is_closed():
        try:
            # Clean up database connections
            from src.shared.database import close_db, close_redis
            _cli_loop.run_until_complete(close_db())
            _cli_loop.run_until_complete(close_redis())
        except Exception:
            pass
        finally:
            _cli_loop.close()
            _cli_loop = None

# Register cleanup at exit
atexit.register(_cleanup_loop)

def run_async(coro):
    """Helper to run async functions in sync context."""
    loop = _get_cli_loop()
    return loop.run_until_complete(coro)


# =============================================================================
# Import and register command groups
# =============================================================================

from src.cli.commands.auth import auth_app
from src.cli.commands.learn import learn_app
from src.cli.commands.profile import profile_app
from src.cli.commands.content import content_app
from src.cli.commands.stats import stats_app
from src.cli.commands.chat import chat_app

app.add_typer(auth_app, name="auth", help="Authentication commands")
app.add_typer(learn_app, name="learn", help="Learning session commands")
app.add_typer(profile_app, name="profile", help="Profile management")
app.add_typer(content_app, name="content", help="Content management")
app.add_typer(stats_app, name="stats", help="Progress and statistics")
app.add_typer(chat_app, name="chat", help="Natural language interface")


# =============================================================================
# Quick access commands (shortcuts for common operations)
# =============================================================================

@app.command("start")
def quick_start(
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
    """Quick start a learning session.

    Shortcut for 'learner learn start'.
    """
    from src.cli.commands.learn import start
    start(minutes=minutes, session_type=session_type)


@app.command("quiz")
def quick_quiz(
    topic: str = typer.Option(None, "--topic", "-t", help="Topic to quiz on"),
    count: int = typer.Option(5, "--count", "-n", help="Number of questions"),
) -> None:
    """Quick start a quiz.

    Starts a quiz on the specified topic or recent learning.
    """
    from src.cli.state import get_current_user_id, require_auth

    require_auth()
    user_id = get_current_user_id()

    console.print(Panel.fit(
        "[bold blue]Quick Quiz[/bold blue]",
        border_style="blue",
    ))

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
                topics=[topic] if topic else ["recent"],
                question_count=count,
            ))

        console.print(Panel(
            response.message,
            title="[bold blue]Assessment[/bold blue]",
            border_style="blue",
        ))

        # Interactive quiz loop
        question_num = 1
        while question_num <= count:
            answer = Prompt.ask(f"\n[bold]Your answer[/bold]")

            if answer.lower() in ("quit", "exit", "q"):
                console.print("[yellow]Quiz ended.[/yellow]")
                break

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description="Evaluating...", total=None)
                response = run_async(orchestrator.route_message(
                    user_id=user_id,
                    message=answer,
                ))

            console.print(Panel(
                response.message,
                title="[bold blue]Assessment[/bold blue]",
                border_style="blue",
            ))

            question_num += 1

        console.print("\n[green]Quiz complete![/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("explain")
def quick_explain(
    topic: str = typer.Argument(..., help="Topic to explain"),
) -> None:
    """Quick start a Feynman explanation exercise.

    Test your understanding by explaining a topic.
    """
    from src.cli.state import get_current_user_id, require_auth

    require_auth()
    user_id = get_current_user_id()

    console.print(Panel.fit(
        f"[bold magenta]Feynman Dialogue: {topic}[/bold magenta]",
        border_style="magenta",
    ))

    console.print(
        "\n[italic]Explain this topic as if teaching someone smart "
        "but unfamiliar with it.[/italic]\n"
    )

    try:
        from src.modules.agents import get_orchestrator

        orchestrator = get_orchestrator()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Starting dialogue...", total=None)
            response = run_async(orchestrator.start_feynman_dialogue(
                user_id=user_id,
                topic=topic,
            ))

        console.print(Panel(
            response.message,
            title="[bold magenta]Socratic Guide[/bold magenta]",
            border_style="magenta",
        ))

        # Interactive explanation loop
        while True:
            explanation = Prompt.ask("\n[bold]Your explanation[/bold]")

            if explanation.lower() in ("quit", "exit", "q", "done"):
                console.print("\n[green]Dialogue complete![/green]")
                break

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description="Analyzing...", total=None)
                response = run_async(orchestrator.route_message(
                    user_id=user_id,
                    message=explanation,
                ))

            console.print(Panel(
                response.message,
                title="[bold magenta]Socratic Guide[/bold magenta]",
                border_style="magenta",
            ))

            if response.end_conversation:
                console.print("\n[green]Excellent explanation![/green]")
                break

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("status")
def quick_status() -> None:
    """Show current status (session, streak, progress).

    Quick overview of your learning status.
    """
    from src.cli.state import get_current_user_id, require_auth

    require_auth()
    user_id = get_current_user_id()

    try:
        from src.modules.session import get_session_service
        from src.modules.user import get_user_service

        session_service = get_session_service()
        user_service = get_user_service()

        # Check for active session
        session = run_async(session_service.get_current_session(user_id))

        console.print(Panel.fit(
            "[bold cyan]Status[/bold cyan]",
            border_style="cyan",
        ))

        # Active session
        if session:
            from datetime import datetime
            elapsed = (datetime.utcnow() - session.started_at).seconds // 60
            console.print(f"\n[green]Active Session:[/green]")
            console.print(f"  Type: {session.session_type.value.title()}")
            console.print(f"  Elapsed: {elapsed} minutes")
        else:
            console.print("\n[dim]No active session[/dim]")

        # Streak
        streak_info = run_async(session_service.get_streak_info(user_id))
        current = streak_info.get("current_streak", 0)

        if current > 0:
            fire = "" * min(current, 5)
            console.print(f"\n{fire} [bold]{current}[/bold] day streak")
        else:
            console.print("\n[dim]No active streak[/dim]")

        if streak_info.get("streak_at_risk"):
            console.print("[yellow]Streak at risk! Study today.[/yellow]")

        # Quick tips
        profile = run_async(user_service.get_profile(user_id))
        if profile and not profile.onboarding_completed:
            console.print("\n[yellow]Complete onboarding: learner profile onboarding[/yellow]")

        if not session:
            console.print("\n[dim]Start learning: learner start[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("config")
def config() -> None:
    """View and validate configuration."""
    from src.shared.config import get_settings

    console.print(Panel.fit(
        "[bold]Configuration[/bold]",
        border_style="cyan",
    ))

    try:
        settings = get_settings()

        console.print("\n[bold]Environment:[/bold]")
        console.print(f"  Mode: {settings.environment}")
        console.print(f"  Log level: {settings.log_level}")

        console.print("\n[bold]LLM Settings:[/bold]")
        console.print(f"  Model: {settings.default_model}")
        console.print(f"  Max tokens: {settings.max_tokens}")
        console.print(f"  Temperature: {settings.temperature}")

        # API keys (masked)
        console.print("\n[bold]API Keys:[/bold]")
        if settings.anthropic_api_key:
            console.print(f"  Anthropic: [green]***{settings.anthropic_api_key[-4:]}[/green]")
        else:
            console.print("  Anthropic: [red]Not set[/red]")

        if settings.youtube_api_key:
            console.print(f"  YouTube: [green]***{settings.youtube_api_key[-4:]}[/green]")

        if settings.github_token:
            console.print(f"  GitHub: [green]***{settings.github_token[-4:]}[/green]")

        console.print("\n[bold]Session Limits:[/bold]")
        console.print(f"  Default: {settings.default_session_minutes} min")
        console.print(f"  Min: {settings.min_session_minutes} min")
        console.print(f"  Max: {settings.max_session_minutes} min")

    except Exception as e:
        console.print(f"[red]Error loading config:[/red] {e}")
        console.print("\n[yellow]Make sure .env file exists with required settings.[/yellow]")
        raise typer.Exit(1)


@app.command("version")
def version() -> None:
    """Show version information."""
    console.print(Panel.fit(
        "[bold]Learner CLI[/bold]\n"
        "Version: 0.1.0\n"
        "AI-powered personalized learning system",
        border_style="cyan",
    ))


@app.callback()
def callback(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
) -> None:
    """Learner - AI-powered personalized learning companion.

    Use 'learner --help' to see all available commands.

    Quick start:
      learner auth login     - Log in to your account
      learner profile onboarding - Set up your profile
      learner start          - Start a learning session
    """
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
