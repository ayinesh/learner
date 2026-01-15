"""GitHub Adapter - Fetches repositories and content from GitHub API."""

from datetime import datetime
from typing import Any

import httpx

from src.modules.content.interface import RawContent, SourceAdapter
from src.shared.config import get_settings
from src.shared.models import SourceType


class GitHubAdapter(SourceAdapter):
    """Adapter for fetching content from GitHub.

    Uses the GitHub API to search for repositories, fetch READMEs,
    and track educational/learning resources.
    """

    GITHUB_API_URL = "https://api.github.com"

    def __init__(self, token: str | None = None) -> None:
        settings = get_settings()
        self._token = token or settings.github_token
        self._headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self._token:
            self._headers["Authorization"] = f"token {self._token}"

    @property
    def source_type(self) -> SourceType:
        return SourceType.GITHUB

    async def fetch_new(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Fetch content from GitHub.

        Config options:
            - query: Search query for repositories
            - topics: List of topics to search
            - language: Programming language filter
            - user: Specific user's repositories
            - org: Specific organization's repositories
            - repo: Specific repository (user/repo format)
            - max_results: Maximum number of results (default 10)
            - sort: Sort by (stars, forks, updated)
            - fetch_readme: Whether to fetch README content (default True)

        Args:
            config: Source configuration
            since: Only fetch repos updated after this

        Returns:
            List of raw content items
        """
        repos: list[RawContent] = []

        if config.get("repo"):
            # Fetch specific repository
            repo = await self._fetch_single_repo(config["repo"], config)
            if repo:
                repos.append(repo)
        elif config.get("user"):
            repos = await self._fetch_user_repos(config, since)
        elif config.get("org"):
            repos = await self._fetch_org_repos(config, since)
        else:
            repos = await self._fetch_search(config, since)

        return repos

    async def validate_config(self, config: dict) -> bool:
        """Validate GitHub configuration.

        Requires at least one of: query, topics, user, org, or repo.
        """
        has_query = bool(config.get("query"))
        has_topics = bool(config.get("topics"))
        has_user = bool(config.get("user"))
        has_org = bool(config.get("org"))
        has_repo = bool(config.get("repo"))

        return has_query or has_topics or has_user or has_org or has_repo

    async def _fetch_search(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Search for repositories."""
        query_parts = []

        # Add search query
        if config.get("query"):
            query_parts.append(config["query"])

        # Add topic filters
        for topic in config.get("topics", []):
            query_parts.append(f"topic:{topic}")

        # Add language filter
        if config.get("language"):
            query_parts.append(f"language:{config['language']}")

        # Add date filter
        if since:
            query_parts.append(f"pushed:>{since.strftime('%Y-%m-%d')}")

        query = " ".join(query_parts)
        if not query:
            return []

        params = {
            "q": query,
            "per_page": min(config.get("max_results", 10), 100),
            "sort": config.get("sort", "stars"),
            "order": "desc",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GITHUB_API_URL}/search/repositories",
                params=params,
                headers=self._headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        repos: list[RawContent] = []
        fetch_readme = config.get("fetch_readme", True)

        for item in data.get("items", []):
            repo = await self._parse_repo(item, fetch_readme)
            if repo:
                repos.append(repo)

        return repos

    async def _fetch_user_repos(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Fetch repositories from a specific user."""
        user = config.get("user")
        if not user:
            return []

        params = {
            "per_page": min(config.get("max_results", 10), 100),
            "sort": config.get("sort", "updated"),
            "direction": "desc",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GITHUB_API_URL}/users/{user}/repos",
                params=params,
                headers=self._headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        repos: list[RawContent] = []
        fetch_readme = config.get("fetch_readme", True)

        for item in data:
            # Filter by date
            if since:
                updated = item.get("pushed_at")
                if updated:
                    updated_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    if updated_at <= since:
                        continue

            repo = await self._parse_repo(item, fetch_readme)
            if repo:
                repos.append(repo)

        return repos

    async def _fetch_org_repos(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Fetch repositories from a specific organization."""
        org = config.get("org")
        if not org:
            return []

        params = {
            "per_page": min(config.get("max_results", 10), 100),
            "sort": config.get("sort", "updated"),
            "direction": "desc",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GITHUB_API_URL}/orgs/{org}/repos",
                params=params,
                headers=self._headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        repos: list[RawContent] = []
        fetch_readme = config.get("fetch_readme", True)

        for item in data:
            if since:
                updated = item.get("pushed_at")
                if updated:
                    updated_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    if updated_at <= since:
                        continue

            repo = await self._parse_repo(item, fetch_readme)
            if repo:
                repos.append(repo)

        return repos

    async def _fetch_single_repo(
        self,
        repo_path: str,
        config: dict,
    ) -> RawContent | None:
        """Fetch a single repository."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GITHUB_API_URL}/repos/{repo_path}",
                headers=self._headers,
                timeout=30.0,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()

        fetch_readme = config.get("fetch_readme", True)
        return await self._parse_repo(data, fetch_readme)

    async def _parse_repo(
        self,
        item: dict,
        fetch_readme: bool = True,
    ) -> RawContent | None:
        """Parse a repository item into RawContent."""
        try:
            full_name = item.get("full_name", "")
            name = item.get("name", "")
            description = item.get("description", "") or ""
            owner = item.get("owner", {})

            if not full_name:
                return None

            # Parse dates
            created_at = None
            created_str = item.get("created_at")
            if created_str:
                try:
                    created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                except ValueError:
                    pass

            updated_at = None
            updated_str = item.get("pushed_at") or item.get("updated_at")
            if updated_str:
                try:
                    updated_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                except ValueError:
                    pass

            # Fetch README if requested
            readme_content = ""
            if fetch_readme:
                readme_content = await self._fetch_readme(full_name)

            # Build content from description + README
            content = description
            if readme_content:
                content = f"{description}\n\n---\n\n{readme_content}"

            return RawContent(
                source_type=SourceType.GITHUB,
                source_url=item.get("html_url", f"https://github.com/{full_name}"),
                title=f"{name}: {description[:100]}" if description else name,
                content=content,
                author=owner.get("login", ""),
                published_at=created_at,
                metadata={
                    "full_name": full_name,
                    "owner": owner.get("login", ""),
                    "language": item.get("language", ""),
                    "topics": item.get("topics", []),
                    "stars": item.get("stargazers_count", 0),
                    "forks": item.get("forks_count", 0),
                    "watchers": item.get("watchers_count", 0),
                    "open_issues": item.get("open_issues_count", 0),
                    "license": (item.get("license") or {}).get("name", ""),
                    "default_branch": item.get("default_branch", "main"),
                    "updated_at": updated_at.isoformat() if updated_at else None,
                    "is_fork": item.get("fork", False),
                    "is_archived": item.get("archived", False),
                },
            )
        except Exception:
            return None

    async def _fetch_readme(self, repo_path: str) -> str:
        """Fetch README content for a repository."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.GITHUB_API_URL}/repos/{repo_path}/readme",
                    headers={
                        **self._headers,
                        "Accept": "application/vnd.github.v3.raw",
                    },
                    timeout=15.0,
                )
                if response.status_code == 200:
                    # Limit README size
                    content = response.text[:10000]
                    return content
        except Exception:
            pass
        return ""


# Factory function
_github_adapter: GitHubAdapter | None = None


def get_github_adapter() -> GitHubAdapter:
    """Get GitHub adapter singleton."""
    global _github_adapter
    if _github_adapter is None:
        _github_adapter = GitHubAdapter()
    return _github_adapter
