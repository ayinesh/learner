"""Twitter/X Adapter - Fetches tweets from Twitter API v2."""

from datetime import datetime
from typing import Any

import httpx

from src.modules.content.interface import RawContent, SourceAdapter
from src.shared.config import get_settings
from src.shared.models import SourceType


class TwitterAdapter(SourceAdapter):
    """Adapter for fetching content from Twitter/X.

    Uses the Twitter API v2 to search for tweets and fetch user timelines.
    Requires Bearer Token authentication.
    """

    TWITTER_API_URL = "https://api.twitter.com/2"

    def __init__(self, bearer_token: str | None = None) -> None:
        settings = get_settings()
        self._bearer_token = bearer_token or settings.twitter_bearer_token
        self._headers = {}
        if self._bearer_token:
            self._headers["Authorization"] = f"Bearer {self._bearer_token}"

    @property
    def source_type(self) -> SourceType:
        return SourceType.TWITTER

    async def fetch_new(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Fetch tweets from Twitter.

        Config options:
            - query: Search query string (supports Twitter search operators)
            - username: Specific user's tweets to fetch
            - user_id: Specific user ID to fetch tweets from
            - list_id: Twitter list ID to fetch tweets from
            - max_results: Maximum number of results (default 10, max 100)
            - include_replies: Whether to include replies (default False)
            - include_retweets: Whether to include retweets (default False)

        Args:
            config: Source configuration
            since: Only fetch tweets newer than this

        Returns:
            List of raw content items
        """
        if not self._bearer_token:
            return []

        tweets: list[RawContent] = []

        if config.get("username"):
            tweets = await self._fetch_user_tweets(config, since)
        elif config.get("user_id"):
            tweets = await self._fetch_user_tweets_by_id(config, since)
        elif config.get("list_id"):
            tweets = await self._fetch_list_tweets(config, since)
        else:
            tweets = await self._fetch_search(config, since)

        return tweets

    async def validate_config(self, config: dict) -> bool:
        """Validate Twitter configuration.

        Requires at least one of: query, username, user_id, or list_id.
        """
        has_query = bool(config.get("query"))
        has_username = bool(config.get("username"))
        has_user_id = bool(config.get("user_id"))
        has_list_id = bool(config.get("list_id"))

        return has_query or has_username or has_user_id or has_list_id

    async def _fetch_search(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Search for tweets using Twitter search API."""
        query = config.get("query", "")
        if not query:
            return []

        # Build query with filters
        if not config.get("include_replies", False):
            query += " -is:reply"
        if not config.get("include_retweets", False):
            query += " -is:retweet"

        params = {
            "query": query,
            "max_results": min(config.get("max_results", 10), 100),
            "tweet.fields": "created_at,public_metrics,author_id,conversation_id,entities,lang",
            "expansions": "author_id,attachments.media_keys",
            "user.fields": "name,username,profile_image_url,verified",
            "media.fields": "url,preview_image_url,type",
        }

        if since:
            params["start_time"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.TWITTER_API_URL}/tweets/search/recent",
                params=params,
                headers=self._headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_tweets(data)

    async def _fetch_user_tweets(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Fetch tweets from a specific user by username."""
        username = config.get("username")
        if not username:
            return []

        # First, get user ID from username
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.TWITTER_API_URL}/users/by/username/{username}",
                headers=self._headers,
                timeout=30.0,
            )
            if response.status_code == 404:
                return []
            response.raise_for_status()
            user_data = response.json()

        user_id = user_data.get("data", {}).get("id")
        if not user_id:
            return []

        config["user_id"] = user_id
        return await self._fetch_user_tweets_by_id(config, since)

    async def _fetch_user_tweets_by_id(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Fetch tweets from a specific user by user ID."""
        user_id = config.get("user_id")
        if not user_id:
            return []

        params = {
            "max_results": min(config.get("max_results", 10), 100),
            "tweet.fields": "created_at,public_metrics,author_id,conversation_id,entities,lang",
            "expansions": "author_id,attachments.media_keys",
            "user.fields": "name,username,profile_image_url,verified",
            "media.fields": "url,preview_image_url,type",
        }

        # Exclude replies/retweets if specified
        excludes = []
        if not config.get("include_replies", False):
            excludes.append("replies")
        if not config.get("include_retweets", False):
            excludes.append("retweets")
        if excludes:
            params["exclude"] = ",".join(excludes)

        if since:
            params["start_time"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.TWITTER_API_URL}/users/{user_id}/tweets",
                params=params,
                headers=self._headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_tweets(data)

    async def _fetch_list_tweets(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Fetch tweets from a Twitter list."""
        list_id = config.get("list_id")
        if not list_id:
            return []

        params = {
            "max_results": min(config.get("max_results", 10), 100),
            "tweet.fields": "created_at,public_metrics,author_id,conversation_id,entities,lang",
            "expansions": "author_id,attachments.media_keys",
            "user.fields": "name,username,profile_image_url,verified",
            "media.fields": "url,preview_image_url,type",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.TWITTER_API_URL}/lists/{list_id}/tweets",
                params=params,
                headers=self._headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        tweets = self._parse_tweets(data)

        # Filter by date if specified
        if since:
            tweets = [t for t in tweets if t.published_at and t.published_at > since]

        return tweets

    def _parse_tweets(self, data: dict) -> list[RawContent]:
        """Parse Twitter API response into RawContent items."""
        tweets: list[RawContent] = []

        # Build user lookup from includes
        users = {}
        for user in data.get("includes", {}).get("users", []):
            users[user["id"]] = user

        # Build media lookup from includes
        media = {}
        for m in data.get("includes", {}).get("media", []):
            media[m["media_key"]] = m

        for tweet in data.get("data", []):
            parsed = self._parse_tweet(tweet, users, media)
            if parsed:
                tweets.append(parsed)

        return tweets

    def _parse_tweet(
        self,
        tweet: dict,
        users: dict,
        media: dict,
    ) -> RawContent | None:
        """Parse a single tweet into RawContent."""
        try:
            tweet_id = tweet.get("id", "")
            text = tweet.get("text", "")
            author_id = tweet.get("author_id", "")

            if not tweet_id or not text:
                return None

            # Get author info
            author = users.get(author_id, {})
            username = author.get("username", "")
            display_name = author.get("name", "")

            # Parse created_at
            published_at = None
            created_at = tweet.get("created_at")
            if created_at:
                try:
                    published_at = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            # Get metrics
            metrics = tweet.get("public_metrics", {})

            # Extract URLs from entities
            urls = []
            entities = tweet.get("entities", {})
            for url_entity in entities.get("urls", []):
                expanded = url_entity.get("expanded_url", "")
                if expanded:
                    urls.append(expanded)

            # Extract hashtags
            hashtags = [
                tag.get("tag", "")
                for tag in entities.get("hashtags", [])
            ]

            # Extract mentions
            mentions = [
                mention.get("username", "")
                for mention in entities.get("mentions", [])
            ]

            # Build tweet URL
            tweet_url = f"https://twitter.com/{username}/status/{tweet_id}" if username else ""

            return RawContent(
                source_type=SourceType.TWITTER,
                source_url=tweet_url,
                title=f"Tweet by @{username}" if username else f"Tweet {tweet_id}",
                content=text,
                author=f"@{username}" if username else "",
                published_at=published_at,
                metadata={
                    "tweet_id": tweet_id,
                    "author_id": author_id,
                    "author_username": username,
                    "author_display_name": display_name,
                    "author_verified": author.get("verified", False),
                    "author_profile_image": author.get("profile_image_url", ""),
                    "conversation_id": tweet.get("conversation_id", ""),
                    "language": tweet.get("lang", ""),
                    "retweet_count": metrics.get("retweet_count", 0),
                    "reply_count": metrics.get("reply_count", 0),
                    "like_count": metrics.get("like_count", 0),
                    "quote_count": metrics.get("quote_count", 0),
                    "impression_count": metrics.get("impression_count", 0),
                    "urls": urls,
                    "hashtags": hashtags,
                    "mentions": mentions,
                },
            )
        except Exception:
            return None


# Factory function
_twitter_adapter: TwitterAdapter | None = None


def get_twitter_adapter() -> TwitterAdapter:
    """Get Twitter adapter singleton."""
    global _twitter_adapter
    if _twitter_adapter is None:
        _twitter_adapter = TwitterAdapter()
    return _twitter_adapter
