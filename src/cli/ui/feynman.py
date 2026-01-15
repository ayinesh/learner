"""Feynman Dialogue Interface - Interactive explanation exercise."""

from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

console = Console()


class FeynmanInterface:
    """Interactive Feynman dialogue interface for the CLI."""

    def __init__(self, topic: str) -> None:
        self.topic = topic
        self.turn = 0
        self.dialogue_history: List[Dict[str, str]] = []
        self.identified_gaps: List[str] = []

    def display_header(self) -> None:
        """Display Feynman exercise header."""
        console.print(Panel.fit(
            f"[bold magenta]Feynman Dialogue: {self.topic}[/bold magenta]",
            border_style="magenta",
        ))

        console.print(
            "\n[italic]The Feynman Technique: Explain a concept as if teaching it to someone "
            "who is smart but unfamiliar with the topic. This reveals gaps in your understanding.[/italic]\n"
        )

        console.print("[dim]Commands: 'quit' to exit, 'done' to finish, 'help' for tips[/dim]\n")

    def display_agent_message(
        self,
        message: str,
        probing_questions: Optional[List[str]] = None,
    ) -> None:
        """Display Socratic agent's message."""
        self.turn += 1

        console.print(Panel(
            message,
            title=f"[bold magenta]Socratic Guide (Turn {self.turn})[/bold magenta]",
            border_style="magenta",
            padding=(1, 2),
        ))

        if probing_questions:
            console.print("\n[yellow]Follow-up questions:[/yellow]")
            for q in probing_questions:
                console.print(f"  ? {q}")

        # Show current gaps if any
        if self.identified_gaps:
            console.print(f"\n[dim]Gaps identified so far: {len(self.identified_gaps)}[/dim]")

    def get_explanation(self) -> tuple[str, bool]:
        """Get user's explanation.

        Returns:
            Tuple of (explanation, should_quit)
        """
        console.print()

        # Multi-line input for explanations
        lines: List[str] = []
        console.print("[bold]Your explanation:[/bold]")
        console.print("[dim]Press Enter twice when done, or type a command.[/dim]")

        empty_count = 0
        while True:
            try:
                line = input("> " if not lines else "  ")

                # Check for commands
                if not lines and line.lower().strip() in ["quit", "q", "exit"]:
                    return "", True
                if not lines and line.lower().strip() in ["done", "finish", "end"]:
                    return "done", False
                if not lines and line.lower().strip() == "help":
                    self._show_help()
                    console.print("\n[bold]Your explanation:[/bold]")
                    continue

                # Track empty lines for exit
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
                return "", True

        explanation = "\n".join(lines).strip()
        return explanation, False

    def _show_help(self) -> None:
        """Show help tips."""
        console.print(Panel(
            "[bold]Tips for the Feynman Technique:[/bold]\n\n"
            "1. [cyan]Use simple language[/cyan] - Avoid jargon and technical terms\n"
            "2. [cyan]Use analogies[/cyan] - Compare to everyday concepts\n"
            "3. [cyan]Identify gaps[/cyan] - If you can't explain something simply, study it more\n"
            "4. [cyan]Organize logically[/cyan] - Build from basics to complex\n"
            "5. [cyan]Be concrete[/cyan] - Use specific examples\n\n"
            "[dim]Commands: 'done' when finished, 'quit' to exit[/dim]",
            title="[bold]Help[/bold]",
            border_style="cyan",
        ))

    def add_dialogue(self, role: str, content: str) -> None:
        """Add to dialogue history."""
        self.dialogue_history.append({
            "role": role,
            "content": content,
        })

    def add_gap(self, gap: str) -> None:
        """Add identified knowledge gap."""
        if gap not in self.identified_gaps:
            self.identified_gaps.append(gap)

    def display_evaluation(
        self,
        completeness: float,
        accuracy: float,
        simplicity: float,
        overall: float,
        feedback: str,
        gaps: Optional[List[str]] = None,
    ) -> None:
        """Display final evaluation."""
        console.print("\n")
        console.print(Panel.fit(
            "[bold green]Explanation Evaluation[/bold green]",
            border_style="green",
        ))

        # Score bars
        scores = [
            ("Completeness", completeness),
            ("Accuracy", accuracy),
            ("Simplicity", simplicity),
            ("Overall", overall),
        ]

        console.print()
        for label, score in scores:
            bar = self._create_bar(score)
            color = "green" if score >= 0.7 else "yellow" if score >= 0.5 else "red"
            console.print(f"  {label:15} [{bar}] [{color}]{score:.0%}[/{color}]")

        console.print()

        # Feedback
        console.print(Panel(
            feedback,
            title="[bold]Feedback[/bold]",
            border_style="cyan",
            padding=(1, 2),
        ))

        # Gaps
        all_gaps = list(set(self.identified_gaps + (gaps or [])))
        if all_gaps:
            console.print("\n[yellow]Areas to review:[/yellow]")
            for gap in all_gaps:
                console.print(f"  - {gap}")

    def _create_bar(self, value: float, width: int = 20) -> str:
        """Create a progress bar."""
        filled = int(value * width)
        empty = width - filled
        return "" * filled + "" * empty

    def display_summary(self) -> None:
        """Display dialogue summary."""
        console.print(Panel.fit(
            "[bold]Dialogue Summary[/bold]",
            border_style="cyan",
        ))

        console.print(f"  Topic: {self.topic}")
        console.print(f"  Turns: {self.turn}")
        console.print(f"  Gaps identified: {len(self.identified_gaps)}")

        if self.dialogue_history:
            user_messages = sum(1 for d in self.dialogue_history if d["role"] == "user")
            console.print(f"  Your explanations: {user_messages}")


def run_feynman_dialogue(
    topic: str,
    initial_prompt: str,
    respond_callback,
    evaluate_callback,
) -> dict:
    """Run an interactive Feynman dialogue session.

    Args:
        topic: Topic to explain
        initial_prompt: Initial prompt from the Socratic agent
        respond_callback: Async function to get agent response
            Takes (user_explanation, dialogue_history) -> dict with:
                - message: Agent response
                - probing_questions: List of follow-up questions
                - gaps: List of identified gaps
                - is_complete: Whether evaluation can be done
        evaluate_callback: Async function to evaluate final explanation
            Takes (dialogue_history) -> dict with scores and feedback

    Returns:
        Dict with evaluation results
    """
    import asyncio

    interface = FeynmanInterface(topic)
    interface.display_header()
    interface.display_agent_message(initial_prompt)

    interface.add_dialogue("agent", initial_prompt)

    while True:
        explanation, should_quit = interface.get_explanation()

        if should_quit:
            console.print("\n[yellow]Dialogue ended.[/yellow]")
            return {"completed": False}

        if explanation == "done" or explanation == "":
            # Request evaluation
            console.print("\n[dim]Evaluating your explanation...[/dim]")
            break

        # Add to history
        interface.add_dialogue("user", explanation)

        # Get agent response
        console.print("\n[dim]Analyzing...[/dim]")

        try:
            loop = asyncio.new_event_loop()
            response = loop.run_until_complete(
                respond_callback(explanation, interface.dialogue_history)
            )
            loop.close()
        except Exception as e:
            console.print(f"[red]Error getting response: {e}[/red]")
            continue

        # Process response
        agent_message = response.get("message", "")
        probing_questions = response.get("probing_questions", [])
        gaps = response.get("gaps", [])

        for gap in gaps:
            interface.add_gap(gap)

        interface.add_dialogue("agent", agent_message)
        interface.display_agent_message(agent_message, probing_questions)

        if response.get("is_complete"):
            console.print("\n[dim]The agent suggests your explanation is complete. Type 'done' to get evaluation.[/dim]")

    # Get final evaluation
    try:
        loop = asyncio.new_event_loop()
        evaluation = loop.run_until_complete(
            evaluate_callback(interface.dialogue_history)
        )
        loop.close()
    except Exception as e:
        console.print(f"[red]Error getting evaluation: {e}[/red]")
        return {"completed": False, "error": str(e)}

    interface.display_evaluation(
        completeness=evaluation.get("completeness_score", 0),
        accuracy=evaluation.get("accuracy_score", 0),
        simplicity=evaluation.get("simplicity_score", 0),
        overall=evaluation.get("overall_score", 0),
        feedback=evaluation.get("feedback", ""),
        gaps=evaluation.get("gaps_identified", []),
    )

    interface.display_summary()

    return {
        "completed": True,
        "topic": topic,
        "turns": interface.turn,
        "evaluation": evaluation,
        "gaps": interface.identified_gaps,
        "dialogue_history": interface.dialogue_history,
    }
