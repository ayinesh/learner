"""Authentication Commands - Login, register, logout, whoami."""

import asyncio
import re
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt

from src.cli.state import get_state_manager, require_auth

auth_app = typer.Typer(help="Authentication commands")
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


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


# Common passwords that should be rejected
_COMMON_PASSWORDS = {
    "password", "12345678", "qwertyui", "letmein1", "welcome1",
    "password1", "admin123", "changeme", "testtest", "trustno1",
}


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength.

    Requirements (must match API validation in src/api/schemas/auth.py):
    - At least 8 characters, max 128
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    - Not in common passwords list

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if len(password) > 128:
        return False, "Password must be at most 128 characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one digit"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_=+\[\]\\;\'`~]', password):
        return False, "Password must contain at least one special character"
    if password.lower() in _COMMON_PASSWORDS:
        return False, "Password is too common. Please choose a stronger password."
    return True, ""


@auth_app.command("register")
def register() -> None:
    """Create a new account."""
    console.print(Panel.fit(
        "[bold green]Create New Account[/bold green]",
        border_style="green",
    ))

    # Get email
    while True:
        email = Prompt.ask("Email")
        if validate_email(email):
            break
        console.print("[red]Invalid email format. Please try again.[/red]")

    # Get password
    while True:
        password = Prompt.ask("Password", password=True)
        valid, error = validate_password(password)
        if valid:
            break
        console.print(f"[red]{error}[/red]")

    # Confirm password
    confirm = Prompt.ask("Confirm password", password=True)
    if password != confirm:
        console.print("[red]Passwords do not match![/red]")
        raise typer.Exit(1)

    try:
        from src.modules.auth import get_auth_service
        from src.modules.user import get_user_service

        auth_service = get_auth_service()
        user_service = get_user_service()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Creating account...", total=None)
            result = run_async(auth_service.register(email, password))

        if not result.success:
            console.print(f"[red]Registration failed:[/red] {result.error}")
            raise typer.Exit(1)

        # Create user profile
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Setting up profile...", total=None)
            run_async(user_service.create_profile(result.user_id))

        # Save tokens to state
        state_manager = get_state_manager()
        state_manager.update_tokens(
            access_token=result.tokens.access_token,
            refresh_token=result.tokens.refresh_token,
            user_id=result.user_id,
            email=email,
            expires_in=result.tokens.expires_in,
        )

        console.print("\n[green]Account created successfully![/green]")
        console.print(f"Logged in as: [cyan]{email}[/cyan]")
        console.print("\n[dim]Run 'learner profile onboarding' to complete your setup.[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@auth_app.command("login")
def login() -> None:
    """Log in to your account."""
    console.print(Panel.fit(
        "[bold cyan]Login[/bold cyan]",
        border_style="cyan",
    ))

    email = Prompt.ask("Email")
    password = Prompt.ask("Password", password=True)

    try:
        from src.modules.auth import get_auth_service

        auth_service = get_auth_service()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Authenticating...", total=None)
            result = run_async(auth_service.login(email, password))

        if not result.success:
            console.print(f"[red]Login failed:[/red] {result.error}")
            raise typer.Exit(1)

        # Save tokens to state
        state_manager = get_state_manager()
        state_manager.update_tokens(
            access_token=result.tokens.access_token,
            refresh_token=result.tokens.refresh_token,
            user_id=result.user_id,
            email=email,
            expires_in=result.tokens.expires_in,
        )

        # Load user's previous session state for personalized welcome
        from src.modules.session.restoration_service import get_restoration_service

        restoration_service = get_restoration_service()
        welcome_ctx = run_async(restoration_service.get_welcome_context(result.user_id))

        # Display personalized welcome message
        console.print()  # Blank line before welcome

        if welcome_ctx.primary_goal:
            # User has learning history - show personalized welcome
            console.print(f"[green]Welcome back![/green] Logged in as [cyan]{email}[/cyan]")
            console.print(f"\n[bold]Learning goal:[/bold] {welcome_ctx.primary_goal}")

            if welcome_ctx.learning_progress > 0:
                progress_pct = int(welcome_ctx.learning_progress * 100)
                console.print(f"[bold]Progress:[/bold] {progress_pct}%")

            if welcome_ctx.current_focus:
                console.print(f"[bold]Current focus:[/bold] {welcome_ctx.current_focus}")

            if welcome_ctx.current_streak > 0:
                streak_emoji = "🔥" if welcome_ctx.current_streak >= 3 else ""
                streak_warning = " [yellow](at risk!)[/yellow]" if welcome_ctx.streak_at_risk else ""
                console.print(f"\n[bold]Streak:[/bold] {welcome_ctx.current_streak} days {streak_emoji}{streak_warning}")

            if welcome_ctx.needs_recovery:
                console.print(f"\n[yellow]It's been {welcome_ctx.days_since_last_session} days since your last session.[/yellow]")
                console.print("[dim]Let's ease back in with a recovery session![/dim]")

            if welcome_ctx.has_active_session:
                console.print("\n[cyan]You have an active session in progress.[/cyan]")
                console.print("[dim]Run 'learner start' to resume.[/dim]")
            else:
                console.print("\n[dim]Run 'learner start' to continue learning.[/dim]")
        else:
            # New user or no learning history
            console.print(f"[green]Welcome back![/green] Logged in as [cyan]{email}[/cyan]")

            # Check if onboarding is needed
            from src.modules.user import get_user_service
            user_service = get_user_service()
            profile = run_async(user_service.get_profile(result.user_id))

            if profile and not profile.onboarding_completed:
                console.print("\n[yellow]Tip:[/yellow] Complete your profile with 'learner profile onboarding'")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@auth_app.command("logout")
def logout() -> None:
    """Log out of your account."""
    state = require_auth()

    from rich.prompt import Confirm

    if not Confirm.ask("Are you sure you want to log out?"):
        raise typer.Exit(0)

    try:
        from src.modules.auth import get_auth_service

        if state.refresh_token:
            auth_service = get_auth_service()
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                progress.add_task(description="Logging out...", total=None)
                run_async(auth_service.logout(state.refresh_token))

        # Clear local state
        state_manager = get_state_manager()
        state_manager.clear()

        console.print("[green]Logged out successfully![/green]")

    except Exception as e:
        # Even if server logout fails, clear local state
        state_manager = get_state_manager()
        state_manager.clear()
        console.print("[yellow]Logged out locally.[/yellow]")


@auth_app.command("whoami")
def whoami() -> None:
    """Show current user information."""
    state = require_auth()

    console.print(Panel.fit(
        "[bold]Current User[/bold]",
        border_style="cyan",
    ))

    console.print(f"Email: [cyan]{state.email}[/cyan]")
    console.print(f"User ID: [dim]{state.user_id}[/dim]")

    if state.token_expires_at:
        from datetime import datetime
        remaining = state.token_expires_at - datetime.utcnow()
        if remaining.total_seconds() > 0:
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            console.print(f"Session expires in: [dim]{hours}h {minutes}m[/dim]")
        else:
            console.print("[yellow]Session expired. Please login again.[/yellow]")


@auth_app.command("refresh")
def refresh() -> None:
    """Refresh authentication tokens."""
    state_manager = get_state_manager()
    state = state_manager.load()

    if not state.refresh_token:
        console.print("[red]No refresh token available. Please login.[/red]")
        raise typer.Exit(1)

    try:
        from src.modules.auth import get_auth_service

        auth_service = get_auth_service()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Refreshing tokens...", total=None)
            result = run_async(auth_service.refresh_tokens(state.refresh_token))

        if not result.success:
            console.print(f"[red]Token refresh failed:[/red] {result.error}")
            console.print("[yellow]Please login again.[/yellow]")
            state_manager.clear()
            raise typer.Exit(1)

        # Update tokens
        state_manager.update_tokens(
            access_token=result.tokens.access_token,
            refresh_token=result.tokens.refresh_token,
            user_id=result.user_id,
            email=state.email or "",
            expires_in=result.tokens.expires_in,
        )

        console.print("[green]Tokens refreshed successfully![/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@auth_app.command("change-password")
def change_password() -> None:
    """Change your password."""
    state = require_auth()

    console.print(Panel.fit(
        "[bold yellow]Change Password[/bold yellow]",
        border_style="yellow",
    ))

    current_password = Prompt.ask("Current password", password=True)

    while True:
        new_password = Prompt.ask("New password", password=True)
        valid, error = validate_password(new_password)
        if valid:
            break
        console.print(f"[red]{error}[/red]")

    confirm = Prompt.ask("Confirm new password", password=True)
    if new_password != confirm:
        console.print("[red]Passwords do not match![/red]")
        raise typer.Exit(1)

    try:
        from src.modules.auth import get_auth_service

        auth_service = get_auth_service()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Changing password...", total=None)
            result = run_async(auth_service.change_password(
                state.user_id,
                current_password,
                new_password,
            ))

        if not result.success:
            console.print(f"[red]Password change failed:[/red] {result.error}")
            raise typer.Exit(1)

        # Clear state - user needs to login again
        state_manager = get_state_manager()
        state_manager.clear()

        console.print("[green]Password changed successfully![/green]")
        console.print("[dim]Please login again with your new password.[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
