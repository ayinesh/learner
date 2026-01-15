"""Prompt Utilities - Rich prompts and inputs."""

from typing import List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()


def create_menu(
    title: str,
    options: List[Tuple[str, str]],
    prompt: str = "Select",
) -> str:
    """Create an interactive menu.

    Args:
        title: Menu title
        options: List of (key, description) tuples
        prompt: Prompt text

    Returns:
        Selected key
    """
    console.print(Panel.fit(f"[bold]{title}[/bold]", border_style="cyan"))

    for key, description in options:
        console.print(f"  [{key}] {description}")

    valid_keys = [opt[0].lower() for opt in options]

    while True:
        choice = Prompt.ask(f"\n{prompt}").strip().lower()
        if choice in valid_keys:
            return choice
        console.print(f"[red]Invalid choice. Please enter one of: {', '.join(valid_keys)}[/red]")


def get_multiline_input(
    prompt_text: str,
    end_marker: str = "",
    max_lines: int = 50,
) -> str:
    """Get multi-line input from user.

    Args:
        prompt_text: Initial prompt to display
        end_marker: Text that signals end of input (empty line by default)
        max_lines: Maximum number of lines to accept

    Returns:
        Multi-line string
    """
    console.print(f"\n[bold]{prompt_text}[/bold]")
    if end_marker:
        console.print(f"[dim]Type '{end_marker}' on a new line to finish.[/dim]")
    else:
        console.print("[dim]Press Enter twice to finish.[/dim]")

    lines: List[str] = []
    empty_count = 0

    while len(lines) < max_lines:
        try:
            line = input()

            # Check for end marker
            if end_marker and line.strip().lower() == end_marker.lower():
                break

            # Check for double empty line (when no end marker)
            if not end_marker:
                if not line.strip():
                    empty_count += 1
                    if empty_count >= 2:
                        break
                else:
                    empty_count = 0

            lines.append(line)

        except EOFError:
            break
        except KeyboardInterrupt:
            console.print("\n[yellow]Input cancelled.[/yellow]")
            return ""

    return "\n".join(lines).strip()


def confirm_action(
    message: str,
    default: bool = True,
) -> bool:
    """Simple confirmation prompt.

    Args:
        message: Confirmation message
        default: Default value if user presses Enter

    Returns:
        True if confirmed, False otherwise
    """
    from rich.prompt import Confirm
    return Confirm.ask(message, default=default)


def select_from_list(
    items: List[str],
    title: str = "Select an item",
    allow_multiple: bool = False,
) -> List[int]:
    """Let user select from a numbered list.

    Args:
        items: List of items to choose from
        title: Title for the selection
        allow_multiple: Allow selecting multiple items

    Returns:
        List of selected indices (0-based)
    """
    console.print(f"\n[bold]{title}[/bold]")

    for i, item in enumerate(items, 1):
        console.print(f"  [{i}] {item}")

    if allow_multiple:
        console.print("\n[dim]Enter numbers separated by commas, or 'all' for all.[/dim]")
        response = Prompt.ask("Selection").strip().lower()

        if response == "all":
            return list(range(len(items)))

        try:
            selections = [int(x.strip()) - 1 for x in response.split(",")]
            return [s for s in selections if 0 <= s < len(items)]
        except ValueError:
            return []
    else:
        while True:
            try:
                selection = int(Prompt.ask("Selection").strip())
                if 1 <= selection <= len(items):
                    return [selection - 1]
                console.print(f"[red]Please enter a number between 1 and {len(items)}[/red]")
            except ValueError:
                console.print("[red]Please enter a valid number[/red]")


def get_rating(
    prompt_text: str,
    min_val: int = 1,
    max_val: int = 5,
) -> int:
    """Get a numeric rating from user.

    Args:
        prompt_text: Prompt to display
        min_val: Minimum value
        max_val: Maximum value

    Returns:
        Selected rating
    """
    from rich.prompt import IntPrompt

    while True:
        try:
            rating = IntPrompt.ask(f"{prompt_text} ({min_val}-{max_val})")
            if min_val <= rating <= max_val:
                return rating
            console.print(f"[red]Please enter a number between {min_val} and {max_val}[/red]")
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")


def display_countdown(
    seconds: int,
    message: str = "Starting in",
) -> None:
    """Display a countdown timer.

    Args:
        seconds: Number of seconds to count down
        message: Message to display
    """
    import time

    for i in range(seconds, 0, -1):
        console.print(f"\r{message} {i}...", end="")
        time.sleep(1)
    console.print("\r" + " " * 30 + "\r", end="")  # Clear line
