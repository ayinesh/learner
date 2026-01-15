"""Reddit Adapter - Fetches posts from Reddit API."""

from datetime import datetime
from typing import Any

import httpx

from src.modules.content.interface import RawContent, SourceAdapter
from src.shared.models import SourceType


class RedditAdapter(SourceAdapter):
    """Adapter for fetching content from Reddit.

    Uses the Reddit JSON API to fetch posts from subreddits.
    Note: Uses public JSON endpoints (no OAuth required for read-only access).
    """

    REDDIT_BASE_URL = "https://www.reddit.com"

    def __init__(self) -> None:
        self._headers = {
            "User-Agent": "Learner/1.0 (Educational Content Aggregator)",
        }

    @property
    def source_type(self) -> SourceType:
        return SourceType.REDDIT

    async def fetch_new(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Fetch posts from Reddit.

        Config options:
            - subreddits: List of subreddit names (without r/)
            - sort: Sort by (hot, new, top, rising)
            - time: Time filter for top (hour, day, week, month, year, all)
            - max_results: Maximum number of results per subreddit (default 10)
            - min_score: Minimum post score to include (default 0)
            - include_comments: Whether to fetch top comments (default False)

        Args:
            config: Source configuration
            since: Only fetch posts newer than this

        Returns:
            List of raw content items
        """
        subreddits = config.get("subreddits", [])
        if not subreddits:
            return []

        posts: list[RawContent] = []

        for subreddit in subreddits:
            try:
                subreddit_posts = await self._fetch_subreddit(
                    subreddit,
                    config,
                    since,
                )
                posts.extend(subreddit_posts)
            except Exception:
                continue

        return posts

    async def validate_config(self, config: dict) -> bool:
        """Validate Reddit configuration.

        Requires at least one subreddit.
        """
        return bool(config.get("subreddits"))

    async def _fetch_subreddit(
        self,
        subreddit: str,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Fetch posts from a specific subreddit."""
        sort = config.get("sort", "hot")
        time = config.get("time", "week")
        limit = min(config.get("max_results", 10), 100)
        min_score = config.get("min_score", 0)
        include_comments = config.get("include_comments", False)

        # Build URL
        url = f"{self.REDDIT_BASE_URL}/r/{subreddit}/{sort}.json"
        params = {"limit": limit}

        if sort == "top":
            params["t"] = time

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers=self._headers,
                timeout=30.0,
                follow_redirects=True,
            )
            response.raise_for_status()
            data = response.json()

        posts: list[RawContent] = []

        for child in data.get("data", {}).get("children", []):
            if child.get("kind") != "t3":  # t3 = link/post
                continue

            post_data = child.get("data", {})

            # Filter by score
            if post_data.get("score", 0) < min_score:
                continue

            # Filter by date
            created_utc = post_data.get("created_utc", 0)
            if created_utc:
                post_date = datetime.utcfromtimestamp(created_utc)
                if since and post_date <= since:
                    continue

            post = await self._parse_post(post_data, subreddit, include_comments)
            if post:
                posts.append(post)

        return posts

    async def _parse_post(
        self,
        post_data: dict,
        subreddit: str,
        include_comments: bool = False,
    ) -> RawContent | None:
        """Parse a Reddit post into RawContent."""
        try:
            post_id = post_data.get("id", "")
            title = post_data.get("title", "")
            selftext = post_data.get("selftext", "")
            author = post_data.get("author", "[deleted]")
            permalink = post_data.get("permalink", "")

            if not post_id or not title:
                return None

            # Build URL
            url = f"{self.REDDIT_BASE_URL}{permalink}" if permalink else ""
            if not url:
                url = f"{self.REDDIT_BASE_URL}/r/{subreddit}/comments/{post_id}"

            # Parse date
            created_at = None
            created_utc = post_data.get("created_utc", 0)
            if created_utc:
                created_at = datetime.utcfromtimestamp(created_utc)

            # Build content
            content = selftext
            if post_data.get("is_self") is False:
                # Link post - include the URL
                link_url = post_data.get("url", "")
                if link_url:
                    content = f"Link: {link_url}\n\n{selftext}"

            # Fetch top comments if requested
            if include_comments and post_id:
                comments = await self._fetch_top_comments(subreddit, post_id)
                if comments:
                    content += f"\n\n---\nTop Comments:\n{comments}"

            return RawContent(
                source_type=SourceType.REDDIT,
                source_url=url,
                title=title,
                content=content,
                author=f"u/{author}",
                published_at=created_at,
                metadata={
                    "post_id": post_id,
                    "subreddit": subreddit,
                    "score": post_data.get("score", 0),
                    "upvote_ratio": post_data.get("upvote_ratio", 0),
                    "num_comments": post_data.get("num_comments", 0),
                    "is_self": post_data.get("is_self", True),
                    "link_flair_text": post_data.get("link_flair_text", ""),
                    "is_original_content": post_data.get("is_original_content", False),
                    "over_18": post_data.get("over_18", False),
                    "spoiler": post_data.get("spoiler", False),
                    "stickied": post_data.get("stickied", False),
                    "link_url": post_data.get("url") if not post_data.get("is_self") else None,
                    "thumbnail": post_data.get("thumbnail", ""),
                },
            )
        except Exception:
            return None

    async def _fetch_top_comments(
        self,
        subreddit: str,
        post_id: str,
        limit: int = 5,
    ) -> str:
        """Fetch top comments for a post."""
        try:
            url = f"{self.REDDIT_BASE_URL}/r/{subreddit}/comments/{post_id}.json"
            params = {"limit": limit, "sort": "top", "depth": 1}

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._headers,
                    timeout=15.0,
                    follow_redirects=True,
                )
                response.raise_for_status()
                data = response.json()

            # Comments are in the second listing
            if len(data) < 2:
                return ""

            comments_data = data[1].get("data", {}).get("children", [])
            comments: list[str] = []

            for child in comments_data[:limit]:
                if child.get("kind") != "t1":  # t1 = comment
                    continue

                comment_data = child.get("data", {})
                body = comment_data.get("body", "")
                author = comment_data.get("author", "[deleted]")
                score = comment_data.get("score", 0)

                if body and author != "[deleted]":
                    # Truncate long comments
                    if len(body) > 500:
                        body = body[:500] + "..."
                    comments.append(f"- {author} ({score} points): {body}")

            return "\n".join(comments)
        except Exception:
            return ""


# Factory function
_reddit_adapter: RedditAdapter | None = None


def get_reddit_adapter() -> RedditAdapter:
    """Get Reddit adapter singleton."""
    global _reddit_adapter
    if _reddit_adapter is None:
        _reddit_adapter = RedditAdapter()
    return _reddit_adapter
