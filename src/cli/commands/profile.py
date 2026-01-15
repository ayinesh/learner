"""Profile Commands - Show, edit, and onboarding."""

import asyncio
from typing import List

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from src.cli.state import get_current_user_id, require_auth
from src.shared.models import SourceType

profile_app = typer.Typer(help="Profile management commands")
console = Console()


def run_async(coro):
    """Helper to run async functions in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@profile_app.command("show")
def show() -> None:
    """Display your profile."""
    require_auth()
    user_id = get_current_user_id()

    try:
        from src.modules.user import get_user_service

        user_service = get_user_service()
        profile = run_async(user_service.get_profile(user_id))

        if not profile:
            console.print("[yellow]No profile found. Run 'learner profile onboarding' to create one.[/yellow]")
            raise typer.Exit(1)

        console.print(Panel.fit(
            "[bold cyan]Your Profile[/bold cyan]",
            border_style="cyan",
        ))

        # Basic info table
        table = Table(show_header=False, box=None)
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Background", profile.background or "[dim]Not set[/dim]")
        table.add_row("Time Budget", f"{profile.time_budget_minutes} minutes/day")
        table.add_row("Timezone", profile.timezone)
        table.add_row(
            "Onboarding",
            "[green]Completed[/green]" if profile.onboarding_completed else "[yellow]Pending[/yellow]"
        )

        console.print(table)

        # Goals
        if profile.goals:
            console.print("\n[bold]Learning Goals:[/bold]")
            for i, goal in enumerate(profile.goals, 1):
                console.print(f"  {i}. {goal}")
        else:
            console.print("\n[dim]No learning goals set[/dim]")

        # Preferred sources
        if profile.preferred_sources:
            console.print("\n[bold]Content Sources:[/bold]")
            sources_str = ", ".join(
                s.value if isinstance(s, SourceType) else str(s)
                for s in profile.preferred_sources
            )
            console.print(f"  {sources_str}")
        else:
            console.print("\n[dim]No content sources configured[/dim]")

        # Timestamps
        console.print(f"\n[dim]Created: {profile.created_at.strftime('%Y-%m-%d %H:%M')}[/dim]")
        console.print(f"[dim]Updated: {profile.updated_at.strftime('%Y-%m-%d %H:%M')}[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@profile_app.command("onboarding")
def onboarding() -> None:
    """Complete the onboarding process."""
    require_auth()
    user_id = get_current_user_id()

    console.print(Panel.fit(
        "[bold green]Welcome to Learner![/bold green]\n"
        "Let's set up your personalized learning experience.",
        border_style="green",
    ))

    # Step 1: Background
    console.print("\n[bold cyan]Step 1/5: Background[/bold cyan]")
    console.print("Tell me about your professional or educational background.")

    background = Prompt.ask(
        "\nYour background",
        default="",
    )

    # Step 2: Experience level
    console.print("\n[bold cyan]Step 2/5: Experience Level[/bold cyan]")
    console.print("What's your experience with AI and Machine Learning?")
    console.print("  [1] None - Complete beginner")
    console.print("  [2] Basic - Understand concepts")
    console.print("  [3] Intermediate - Built simple models")
    console.print("  [4] Advanced - Production ML experience")

    exp_level = IntPrompt.ask(
        "\nYour selection",
        choices=["1", "2", "3", "4"],
        default=2,
    )

    experience_map = {
        1: "Beginner",
        2: "Basic understanding of AI concepts",
        3: "Intermediate - hands-on experience with ML",
        4: "Advanced - production ML experience",
    }
    background = f"{background}. Experience level: {experience_map[exp_level]}"

    # Step 3: Learning goals
    console.print("\n[bold cyan]Step 3/5: Learning Goals[/bold cyan]")
    console.print("What would you like to learn? (Enter each goal, empty line to finish)")

    goals: List[str] = []
    while True:
        goal = Prompt.ask(f"Goal {len(goals) + 1} (or press Enter to finish)")
        if not goal:
            if not goals:
                console.print("[yellow]Please enter at least one goal.[/yellow]")
                continue
            break
        goals.append(goal)
        if len(goals) >= 5:
            console.print("[dim]Maximum 5 goals reached.[/dim]")
            break

    # Step 4: Time budget
    console.print("\n[bold cyan]Step 4/5: Daily Time Budget[/bold cyan]")
    console.print("How many minutes can you dedicate to learning each day?")

    time_budget = IntPrompt.ask(
        "Minutes per day",
        default=30,
    )

    # Validate time budget
    if time_budget < 10:
        console.print("[yellow]Minimum is 10 minutes. Setting to 10.[/yellow]")
        time_budget = 10
    elif time_budget > 180:
        console.print("[yellow]Maximum is 180 minutes. Setting to 180.[/yellow]")
        time_budget = 180

    # Step 5: Content sources
    console.print("\n[bold cyan]Step 5/5: Content Sources[/bold cyan]")
    console.print("Select your preferred content sources:")

    available_sources = [
        (SourceType.ARXIV, "ArXiv - Research papers"),
        (SourceType.BLOG, "Blogs/RSS - Tech blogs and feeds"),
        (SourceType.YOUTUBE, "YouTube - Video tutorials"),
        (SourceType.GITHUB, "GitHub - Code and projects"),
        (SourceType.TWITTER, "Twitter/X - Industry updates"),
    ]

    selected_sources: List[SourceType] = []
    for source, description in available_sources:
        if Confirm.ask(f"  Include {description}?", default=source in [SourceType.ARXIV, SourceType.BLOG]):
            selected_sources.append(source)

    if not selected_sources:
        console.print("[yellow]Selecting ArXiv as default.[/yellow]")
        selected_sources = [SourceType.ARXIV]

    # Timezone
    console.print("\n[bold]Timezone[/bold]")
    import time as time_module
    default_tz = time_module.tzname[0] or "UTC"
    timezone = Prompt.ask("Your timezone", default=default_tz)

    # Confirm
    console.print("\n" + "=" * 50)
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Background: {background[:50]}...")
    console.print(f"  Goals: {', '.join(goals[:3])}...")
    console.print(f"  Time: {time_budget} min/day")
    console.print(f"  Sources: {', '.join(s.value for s in selected_sources)}")
    console.print(f"  Timezone: {timezone}")

    if not Confirm.ask("\nSave this profile?", default=True):
        console.print("[yellow]Onboarding cancelled.[/yellow]")
        raise typer.Exit(0)

    # Save profile
    try:
        from src.modules.user import get_user_service
        from src.modules.user.interface import OnboardingData

        user_service = get_user_service()

        onboarding_data = OnboardingData(
            background=background,
            goals=goals,
            time_budget_minutes=time_budget,
            preferred_sources=selected_sources,
            timezone=timezone,
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Saving profile...", total=None)
            run_async(user_service.complete_onboarding(user_id, onboarding_data))

        console.print("\n[green]Profile saved successfully![/green]")
        console.print("You're all set! Start learning with 'learner learn start'")

    except Exception as e:
        console.print(f"[red]Error saving profile:[/red] {e}")
        raise typer.Exit(1)


@profile_app.command("edit")
def edit(
    background: str = typer.Option(None, "--background", "-b", help="Update background"),
    time_budget: int = typer.Option(None, "--time", "-t", help="Update time budget (minutes)"),
    timezone: str = typer.Option(None, "--timezone", "-z", help="Update timezone"),
) -> None:
    """Edit your profile settings."""
    require_auth()
    user_id = get_current_user_id()

    updates = {}

    if background is not None:
        updates["background"] = background

    if time_budget is not None:
        if time_budget < 10 or time_budget > 180:
            console.print("[red]Time budget must be between 10 and 180 minutes.[/red]")
            raise typer.Exit(1)
        updates["time_budget_minutes"] = time_budget

    if timezone is not None:
        updates["timezone"] = timezone

    if not updates:
        # Interactive edit
        console.print(Panel.fit(
            "[bold]Edit Profile[/bold]",
            border_style="cyan",
        ))
        console.print("[dim]Press Enter to keep current value[/dim]\n")

        try:
            from src.modules.user import get_user_service

            user_service = get_user_service()
            profile = run_async(user_service.get_profile(user_id))

            if not profile:
                console.print("[red]No profile found.[/red]")
                raise typer.Exit(1)

            new_background = Prompt.ask(
                "Background",
                default=profile.background or "",
            )
            if new_background != profile.background:
                updates["background"] = new_background

            new_time = IntPrompt.ask(
                "Time budget (minutes/day)",
                default=profile.time_budget_minutes,
            )
            if new_time != profile.time_budget_minutes:
                updates["time_budget_minutes"] = new_time

            new_tz = Prompt.ask(
                "Timezone",
                default=profile.timezone,
            )
            if new_tz != profile.timezone:
                updates["timezone"] = new_tz

        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

    if not updates:
        console.print("[dim]No changes made.[/dim]")
        return

    try:
        from src.modules.user import get_user_service

        user_service = get_user_service()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Updating profile...", total=None)
            run_async(user_service.update_profile(user_id, **updates))

        console.print("[green]Profile updated successfully![/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@profile_app.command("goals")
def goals(
    add: str = typer.Option(None, "--add", "-a", help="Add a new goal"),
    remove: int = typer.Option(None, "--remove", "-r", help="Remove goal by number"),
) -> None:
    """Manage learning goals."""
    require_auth()
    user_id = get_current_user_id()

    try:
        from src.modules.user import get_user_service

        user_service = get_user_service()
        profile = run_async(user_service.get_profile(user_id))

        if not profile:
            console.print("[red]No profile found.[/red]")
            raise typer.Exit(1)

        current_goals = list(profile.goals)

        if add:
            current_goals.append(add)
            run_async(user_service.update_profile(user_id, goals=current_goals))
            console.print(f"[green]Added goal:[/green] {add}")
            return

        if remove is not None:
            if remove < 1 or remove > len(current_goals):
                console.print(f"[red]Invalid goal number. Choose 1-{len(current_goals)}[/red]")
                raise typer.Exit(1)

            removed = current_goals.pop(remove - 1)
            run_async(user_service.update_profile(user_id, goals=current_goals))
            console.print(f"[yellow]Removed goal:[/yellow] {removed}")
            return

        # Display current goals
        console.print(Panel.fit(
            "[bold]Learning Goals[/bold]",
            border_style="cyan",
        ))

        if current_goals:
            for i, goal in enumerate(current_goals, 1):
                console.print(f"  {i}. {goal}")
            console.print("\n[dim]Use --add 'goal' to add, --remove N to remove[/dim]")
        else:
            console.print("[dim]No goals set.[/dim]")
            console.print("[dim]Use --add 'Your goal' to add a goal.[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@profile_app.command("sources")
def sources(
    add: str = typer.Option(None, "--add", "-a", help="Add a source (arxiv, blog, youtube, github, twitter)"),
    remove: str = typer.Option(None, "--remove", "-r", help="Remove a source"),
) -> None:
    """Manage content sources."""
    require_auth()
    user_id = get_current_user_id()

    try:
        from src.modules.user import get_user_service

        user_service = get_user_service()
        profile = run_async(user_service.get_profile(user_id))

        if not profile:
            console.print("[red]No profile found.[/red]")
            raise typer.Exit(1)

        if add:
            try:
                source = SourceType(add.lower())
            except ValueError:
                console.print(f"[red]Invalid source: {add}[/red]")
                console.print("Valid sources: arxiv, blog, youtube, github, twitter, reddit")
                raise typer.Exit(1)

            run_async(user_service.add_source(user_id, source, {}))
            console.print(f"[green]Added source:[/green] {source.value}")
            return

        if remove:
            try:
                source = SourceType(remove.lower())
            except ValueError:
                console.print(f"[red]Invalid source: {remove}[/red]")
                raise typer.Exit(1)

            run_async(user_service.remove_source(user_id, source))
            console.print(f"[yellow]Removed source:[/yellow] {source.value}")
            return

        # Display current sources
        console.print(Panel.fit(
            "[bold]Content Sources[/bold]",
            border_style="cyan",
        ))

        if profile.preferred_sources:
            console.print("[bold]Active sources:[/bold]")
            for source in profile.preferred_sources:
                source_name = source.value if isinstance(source, SourceType) else str(source)
                console.print(f"  [green]+[/green] {source_name}")
        else:
            console.print("[dim]No sources configured.[/dim]")

        console.print("\n[dim]Available sources: arxiv, blog, youtube, github, twitter, reddit[/dim]")
        console.print("[dim]Use --add source or --remove source[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
