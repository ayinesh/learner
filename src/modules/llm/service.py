"""LLM Service - Anthropic Claude API wrapper."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator

import anthropic
from anthropic import AsyncAnthropic

from src.shared.config import get_settings

settings = get_settings()


@dataclass
class LLMResponse:
    """Response from LLM completion."""

    content: str
    model: str
    usage: dict[str, int]
    stop_reason: str | None = None


@dataclass
class PromptTemplate:
    """Loaded prompt template."""

    name: str
    system: str
    user: str
    variables: list[str]

    def format(self, **kwargs: Any) -> tuple[str, str]:
        """Format template with variables. Returns (system, user) prompts."""
        system = self.system
        user = self.user
        for key, value in kwargs.items():
            system = system.replace(f"{{{{{key}}}}}", str(value))
            user = user.replace(f"{{{{{key}}}}}", str(value))
        return system, user


class LLMService:
    """Service for interacting with Anthropic Claude API."""

    def __init__(self) -> None:
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.default_model = settings.default_model
        self.max_tokens = settings.max_tokens
        self._prompt_cache: dict[str, PromptTemplate] = {}

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Generate a completion from the LLM.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            model: Model to use (defaults to claude-sonnet-4-20250514)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            LLMResponse with content and metadata
        """
        messages = [{"role": "user", "content": prompt}]

        response = await self.client.messages.create(
            model=model or self.default_model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature or settings.temperature,
            system=system_prompt or "",
            messages=messages,
        )

        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            stop_reason=response.stop_reason,
        )

    async def complete_with_history(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Generate completion with conversation history.

        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
            system_prompt: Optional system prompt
            model: Model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            LLMResponse with content and metadata
        """
        response = await self.client.messages.create(
            model=model or self.default_model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature or settings.temperature,
            system=system_prompt or "",
            messages=messages,
        )

        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            stop_reason=response.stop_reason,
        )

    async def stream_complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream completion chunks from the LLM.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            model: Model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Yields:
            Text chunks as they're generated
        """
        messages = [{"role": "user", "content": prompt}]

        async with self.client.messages.stream(
            model=model or self.default_model,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature or settings.temperature,
            system=system_prompt or "",
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def load_prompt_template(self, name: str) -> PromptTemplate:
        """Load a prompt template from the prompts directory.

        Args:
            name: Template name (e.g., "socratic/confused_student")

        Returns:
            PromptTemplate instance
        """
        if name in self._prompt_cache:
            return self._prompt_cache[name]

        # Security: Validate template name to prevent path traversal attacks
        # Only allow alphanumeric, underscores, hyphens, and forward slashes for subdirectories
        if not re.match(r'^[a-zA-Z0-9_/\-]+$', name):
            raise ValueError(f"Invalid template name: {name}. Only alphanumeric, underscore, hyphen, and slash allowed.")

        # Security: Prevent path traversal attempts
        if '..' in name or name.startswith('/') or name.startswith('\\'):
            raise ValueError(f"Invalid template name: {name}. Path traversal not allowed.")

        # Go up from llm -> modules -> src -> project root
        prompts_dir = Path(__file__).parent.parent.parent.parent / "prompts"
        template_path = prompts_dir / f"{name}.txt"

        # Security: Ensure resolved path is within prompts directory
        try:
            resolved_path = template_path.resolve()
            prompts_resolved = prompts_dir.resolve()
            if not str(resolved_path).startswith(str(prompts_resolved)):
                raise ValueError(f"Invalid template path: {name}. Must be within prompts directory.")
        except (OSError, ValueError) as e:
            raise ValueError(f"Invalid template name: {name}") from e

        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {name}")

        content = template_path.read_text()

        # Parse template format:
        # ---SYSTEM---
        # system prompt here
        # ---USER---
        # user prompt here
        # ---VARIABLES---
        # var1, var2, var3

        parts = content.split("---")
        system = ""
        user = ""
        variables: list[str] = []

        current_section = None
        for part in parts:
            part = part.strip()
            if part == "SYSTEM":
                current_section = "system"
            elif part == "USER":
                current_section = "user"
            elif part == "VARIABLES":
                current_section = "variables"
            elif current_section == "system":
                system = part
            elif current_section == "user":
                user = part
            elif current_section == "variables":
                variables = [v.strip() for v in part.split(",") if v.strip()]

        template = PromptTemplate(name=name, system=system, user=user, variables=variables)
        self._prompt_cache[name] = template
        return template


# Singleton instance
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
