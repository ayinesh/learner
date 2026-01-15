"""Content Commands - Feed, search, and content management."""

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

from src.cli.state import get_current_user_id, require_auth
from src.cli.ui.display import display_content_card
from src.shared.models import SourceType

content_app = typer.Typer(help="Content management commands")
console = Console()


def run_async(coro):
    """Helper to run async functions in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@content_app.command("feed")
def feed(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of items"),
    source: str = typer.Option(None, "--source", "-s", help="Filter by source type"),
) -> None:
    """View personalized content feed."""
    require_auth()
    user_id = get_current_user_id()

    console.print(Panel.fit(
        "[bold]Content Feed[/bold]",
        border_style="cyan",
    ))

    # Parse source filter
    source_types = None
    if source:
        try:
            source_types = [SourceType(source.lower())]
        except ValueError:
            console.print(f"[red]Invalid source: {source}[/red]")
            console.print("Valid sources: arxiv, blog, youtube, github, twitter, reddit")
            raise typer.Exit(1)

    try:
        from src.modules.content import get_content_service

        service = get_content_service()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Loading feed...", total=None)
            content = run_async(service.get_relevant_content(
                user_id=user_id,
                limit=limit,
                source_types=source_types,
            ))

        if not content:
            console.print("\n[dim]No content found.[/dim]")
            console.print("Try fetching content with 'learner content fetch arxiv'")
            return

        for i, item in enumerate(content, 1):
            display_content_card(item, i)

        console.print(f"\n[dim]Showing {len(content)} items. Use --limit to see more.[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@content_app.command("search")
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
) -> None:
    """Search content."""
    require_auth()
    user_id = get_current_user_id()

    console.print(f"[bold]Searching:[/bold] {query}")

    try:
        from src.modules.content import get_content_service

        service = get_content_service()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Searching...", total=None)
            results = run_async(service.search_content(
                query=query,
                user_id=user_id,
                limit=limit,
            ))

        if not results:
            console.print("\n[dim]No results found.[/dim]")
            return

        console.print(f"\n[green]Found {len(results)} results:[/green]")

        for i, item in enumerate(results, 1):
            display_content_card(item, i)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@content_app.command("fetch")
def fetch(
    source: str = typer.Argument(..., help="Source type (arxiv, rss)"),
    max_items: int = typer.Option(10, "--max", "-m", help="Max items to fetch"),
) -> None:
    """Fetch content from a source."""
    require_auth()
    user_id = get_current_user_id()

    console.print(f"[bold]Fetching from:[/bold] {source}")

    try:
        from src.modules.content import get_content_service

        service = get_content_service()

        # Build config based on source
        if source.lower() == "arxiv":
            categories = Prompt.ask(
                "ArXiv categories",
                default="cs.AI,cs.LG",
            ).split(",")

            config = {
                "categories": [c.strip() for c in categories],
                "max_results": max_items,
            }
            source_type = SourceType.ARXIV

        elif source.lower() == "rss":
            feed_url = Prompt.ask(
                "RSS feed URL",
                default="https://news.ycombinator.com/rss",
            )

            config = {
                "feed_urls": [feed_url],
                "max_items": max_items,
            }
            source_type = SourceType.BLOG

        else:
            console.print(f"[red]Unknown source type: {source}[/red]")
            console.print("Supported sources: arxiv, rss")
            raise typer.Exit(1)

        # Fetch content
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description=f"Fetching from {source}...", total=None)
            content_ids = run_async(service.ingest_from_source(
                source_type=source_type,
                config=config,
                user_id=user_id,
            ))

        console.print(f"\n[green]Ingested {len(content_ids)} items[/green]")

        # Process content
        if content_ids:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    description="Processing content...",
                    total=len(content_ids),
                )
                for cid in content_ids:
                    run_async(service.process_content(cid))
                    progress.advance(task)

            console.print(f"[green]Processed {len(content_ids)} items[/green]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@content_app.command("show")
def show(
    content_id: str = typer.Argument(..., help="Content ID to display"),
) -> None:
    """Show content details."""
    require_auth()
    user_id = get_current_user_id()

    try:
        from uuid import UUID
        from src.modules.content import get_content_service

        cid = UUID(content_id)
        service = get_content_service()

        content = run_async(service.get_content(cid))

        if not content:
            console.print("[red]Content not found.[/red]")
            raise typer.Exit(1)

        console.print(Panel.fit(
            f"[bold cyan]{content.title}[/bold cyan]",
            border_style="cyan",
        ))

        table = Table(show_header=False, box=None)
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Source", content.source_type.value.upper())
        table.add_row("Difficulty", f"{content.difficulty_level}/5")
        table.add_row("Relevance", f"{content.relevance_score:.0%}")
        table.add_row("URL", content.source_url)
        table.add_row("Created", content.created_at.strftime("%Y-%m-%d %H:%M"))

        console.print(table)

        # Topics
        if content.topics:
            console.print(f"\n[bold]Topics:[/bold] {', '.join(content.topics)}")

        # Summary
        console.print("\n[bold]Summary:[/bold]")
        console.print(content.summary)

    except ValueError:
        console.print("[red]Invalid content ID format.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@content_app.command("rate")
def rate(
    content_id: str = typer.Argument(..., help="Content ID to rate"),
    rating: int = typer.Option(None, "--rating", "-r", help="Rating (1-5)"),
) -> None:
    """Rate content relevance."""
    require_auth()
    user_id = get_current_user_id()

    try:
        from uuid import UUID
        from src.modules.content import get_content_service

        cid = UUID(content_id)

        if rating is None:
            rating = IntPrompt.ask(
                "How relevant was this content? (1-5)",
                choices=["1", "2", "3", "4", "5"],
            )

        if rating < 1 or rating > 5:
            console.print("[red]Rating must be between 1 and 5.[/red]")
            raise typer.Exit(1)

        notes = Prompt.ask("Any notes? (optional)", default="")

        service = get_content_service()

        run_async(service.record_feedback(
            user_id=user_id,
            content_id=cid,
            relevance_rating=rating,
            notes=notes if notes else None,
        ))

        console.print(f"[green]Rated {rating}/5. Thanks for the feedback![/green]")

    except ValueError:
        console.print("[red]Invalid content ID format.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@content_app.command("topics")
def topics() -> None:
    """View content topics."""
    require_auth()
    user_id = get_current_user_id()

    console.print(Panel.fit(
        "[bold]Content Topics[/bold]",
        border_style="cyan",
    ))

    try:
        from src.modules.content import get_content_service

        service = get_content_service()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(description="Loading topics...", total=None)
            topics = run_async(service.get_user_topics(user_id))

        if not topics:
            console.print("\n[dim]No topics found.[/dim]")
            console.print("Topics are extracted from content you fetch and consume.")
            return

        console.print()

        for topic in topics[:20]:  # Show top 20
            topic_name = topic.get("name", "Unknown")
            count = topic.get("content_count", 0)
            console.print(f"  {topic_name}: {count} items")

        if len(topics) > 20:
            console.print(f"\n[dim]...and {len(topics) - 20} more[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@content_app.command("sources")
def sources() -> None:
    """View configured content sources."""
    require_auth()
    user_id = get_current_user_id()

    console.print(Panel.fit(
        "[bold]Content Sources[/bold]",
        border_style="cyan",
    ))

    try:
        from src.modules.user import get_user_service

        user_service = get_user_service()
        profile = run_async(user_service.get_profile(user_id))

        if not profile or not profile.preferred_sources:
            console.print("\n[dim]No sources configured.[/dim]")
            console.print("Add sources with 'learner profile sources --add <source>'")
            return

        console.print("\n[bold]Active Sources:[/bold]")

        for source in profile.preferred_sources:
            source_name = source.value if isinstance(source, SourceType) else str(source)

            # Get source config
            try:
                source_enum = source if isinstance(source, SourceType) else SourceType(source)
                config = run_async(user_service.get_source_config(user_id, source_enum))
                config_str = f" [dim]({len(config or {})} settings)[/dim]"
            except Exception:
                config_str = ""

            console.print(f"  [green]+[/green] {source_name}{config_str}")

        console.print("\n[dim]Manage with 'learner profile sources'[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
