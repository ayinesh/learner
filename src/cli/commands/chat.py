"""Natural Language Chat Commands - Talk to Learner in plain English.

This module provides a conversational interface to the Learner CLI,
allowing users to execute commands using natural language instead
of remembering exact command syntax.

Usage:
    learner chat ask "start a 30 minute session"
    learner chat ask "quiz me on transformers"
    learner chat examples
"""

import asyncio
import logging
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from src.cli.state import get_state_manager
from src.shared.exceptions import (
    CommandNotFoundError,
    NLPParseError,
    ValidationError,
)
from src.shared.feature_flags import FeatureFlags, get_feature_flags

logger = logging.getLogger(__name__)

chat_app = typer.Typer(
    help="Natural language interface - talk to Learner in plain English",
    no_args_is_help=True,
)
console = Console()


def run_async(coro):
    """Helper to run async functions in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@chat_app.command("ask")
def ask(
    message: str = typer.Argument(
        ...,
        help="What do you want to do? (in natural language)",
    ),
    confirm: bool = typer.Option(
        True,
        "--confirm/--no-confirm",
        "-c/-C",
        help="Confirm before executing (default: yes)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation even for destructive actions",
    ),
) -> None:
    """Execute commands using natural language.

    Talk to Learner like you would to a person. The system will
    understand your intent and execute the appropriate command.

    Examples:
        learner chat ask "start a 30 minute session"
        learner chat ask "show my progress"
        learner chat ask "quiz me on transformers"
        learner chat ask "end my session" --no-confirm
    """
    # Check feature flag
    flags = get_feature_flags()
    if not flags.is_enabled(FeatureFlags.ENABLE_NLP_COMMANDS):
        console.print(
            "[yellow]NLP commands are not enabled.[/yellow]\n\n"
            "To enable, set the environment variable:\n"
            "  [cyan]FF_ENABLE_NLP_COMMANDS=true[/cyan]\n\n"
            "Or use the standard CLI commands:\n"
            "  [dim]learner --help[/dim]"
        )
        raise typer.Exit(1)

    # Load state to check authentication
    state_manager = get_state_manager()
    state = state_manager.load()

    try:
        # Import parser (lazy to avoid circular imports)
        from src.cli.nlp_parser import get_nlp_parser

        parser = get_nlp_parser()

        # Parse the natural language command
        console.print(f"[dim]Processing: {message[:50]}{'...' if len(message) > 50 else ''}[/dim]\n")

        intent = run_async(parser.parse_command(
            user_input=message,
            is_authenticated=state.is_authenticated,
        ))

        # Display what we understood
        console.print(Panel.fit(
            f"[bold cyan]Understood:[/bold cyan] {intent.description}\n\n"
            f"[dim]Equivalent command:[/dim] [dim italic]{intent.command_signature}[/dim italic]",
            border_style="cyan",
        ))

        # Handle confirmation
        should_confirm = confirm and intent.needs_confirmation and not force

        if should_confirm:
            console.print()
            if intent.command in parser.DESTRUCTIVE_COMMANDS:
                console.print("[yellow]This action will modify your data.[/yellow]")

            if not Confirm.ask("Execute this command?"):
                console.print("[dim]Cancelled.[/dim]")
                raise typer.Exit(0)

        # Execute the command
        console.print()
        try:
            result = intent.execute()

            # Show success message if command didn't output anything
            if result and result.get("message"):
                console.print(Panel(
                    f"[green]{result['message']}[/green]",
                    title="[bold green]Done[/bold green]",
                    border_style="green",
                ))

        except typer.Exit:
            # Command handled its own exit
            raise
        except Exception as e:
            console.print(f"[red]Command failed:[/red] {e}")
            raise typer.Exit(1)

    except ValidationError as e:
        console.print(f"[red]Invalid input:[/red] {e.message}")
        _show_help_hint()
        raise typer.Exit(1)

    except NLPParseError as e:
        console.print(f"[red]I didn't understand that:[/red] {e.message}")
        _show_help_hint()
        raise typer.Exit(1)

    except CommandNotFoundError as e:
        console.print(f"[red]Unknown command:[/red] {e.message}")
        _show_help_hint()
        raise typer.Exit(1)

    except Exception as e:
        logger.exception("Unexpected error in NLP command")
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@chat_app.command("examples")
def examples() -> None:
    """Show example natural language commands.

    Displays categorized examples of what you can say to Learner
    using natural language.
    """
    console.print(Panel.fit(
        "[bold cyan]Natural Language Examples[/bold cyan]\n\n"
        "[dim]Say these (or similar phrases) after 'learner chat ask'[/dim]",
        border_style="cyan",
    ))

    # Learning Sessions
    console.print("\n[bold green]Learning Sessions[/bold green]")
    session_examples = [
        ("start a learning session for 45 minutes", "Starts a 45-min regular session"),
        ("begin a drill session", "Starts a drill-focused session"),
        ("start a quick 20 minute catchup", "Starts a catchup session"),
        ("show session status", "Displays current session info"),
        ("end my current session", "Ends the active session"),
    ]
    _print_examples(session_examples)

    # Assessment
    console.print("\n[bold blue]Assessment & Quizzes[/bold blue]")
    quiz_examples = [
        ("quiz me on attention mechanisms", "Quiz on specific topic"),
        ("give me a quick 5 question quiz", "Quick assessment"),
        ("test my knowledge of Python", "Topic-focused quiz"),
        ("explain transformers", "Start Feynman dialogue"),
        ("teach me about neural networks", "Explanation mode"),
    ]
    _print_examples(quiz_examples)

    # Progress & Stats
    console.print("\n[bold yellow]Progress & Statistics[/bold yellow]")
    stats_examples = [
        ("show my stats", "Learning progress overview"),
        ("how am I doing?", "Progress summary"),
        ("what's my streak?", "Streak information"),
        ("show my learning history", "Session history"),
    ]
    _print_examples(stats_examples)

    # Content
    console.print("\n[bold magenta]Content Discovery[/bold magenta]")
    content_examples = [
        ("find papers about reinforcement learning", "Search research content"),
        ("recommend content for LLMs", "Get suggestions"),
        ("search for transformer tutorials", "Find learning materials"),
    ]
    _print_examples(content_examples)

    # Profile & Account
    console.print("\n[bold red]Profile & Account[/bold red]")
    account_examples = [
        ("show my profile", "View profile settings"),
        ("who am I?", "Current user info"),
        ("log out", "End session (requires confirm)"),
    ]
    _print_examples(account_examples)

    # Tips
    console.print("\n[dim]" + "-" * 60 + "[/dim]")
    console.print("\n[bold]Tips:[/bold]")
    console.print("  - You can phrase commands naturally - exact wording doesn't matter")
    console.print("  - Destructive actions (logout, end session) will ask for confirmation")
    console.print("  - Use [cyan]--no-confirm[/cyan] to skip confirmation prompts")
    console.print("  - Use [cyan]--force[/cyan] to skip even destructive confirmations")
    console.print("\n[dim]You can also use the standard CLI commands: learner --help[/dim]")


@chat_app.command("intents")
def intents() -> None:
    """Show all available command intents (developer info).

    Lists all the intents that the NLP parser can recognize
    and their corresponding CLI commands.
    """
    console.print(Panel.fit(
        "[bold]Available Command Intents[/bold]",
        border_style="cyan",
    ))

    table = Table(show_header=True, header_style="bold")
    table.add_column("Intent", style="cyan")
    table.add_column("CLI Command")
    table.add_column("Destructive", justify="center")

    intent_data = [
        ("learn.start", "learner learn start", False),
        ("learn.status", "learner learn status", False),
        ("learn.end", "learner learn end", True),
        ("quiz.start", "learner quiz", False),
        ("explain.start", "learner explain", False),
        ("stats.show", "learner stats progress", False),
        ("profile.show", "learner profile show", False),
        ("content.search", "learner content search", False),
        ("auth.logout", "learner auth logout", True),
        ("auth.whoami", "learner auth whoami", False),
    ]

    for intent, cli_cmd, destructive in intent_data:
        dest_marker = "[red]Yes[/red]" if destructive else "[green]No[/green]"
        table.add_row(intent, cli_cmd, dest_marker)

    console.print()
    console.print(table)
    console.print("\n[dim]Destructive commands require confirmation by default.[/dim]")


def _print_examples(examples: list[tuple[str, str]]) -> None:
    """Print a list of examples with descriptions."""
    for example, description in examples:
        console.print(f"  [cyan]\"{example}\"[/cyan]")
        console.print(f"    [dim]{description}[/dim]")


def _show_help_hint() -> None:
    """Show a hint to get help."""
    console.print("\n[dim]Try 'learner chat examples' to see what I can understand.[/dim]")
