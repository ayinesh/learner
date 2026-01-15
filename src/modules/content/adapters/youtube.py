"""YouTube Adapter - Fetches videos from YouTube Data API."""

from datetime import datetime
from typing import Any

import httpx

from src.modules.content.interface import RawContent, SourceAdapter
from src.shared.config import get_settings
from src.shared.models import SourceType


class YouTubeAdapter(SourceAdapter):
    """Adapter for fetching videos from YouTube.

    Uses the YouTube Data API v3 to search for educational videos
    based on topics, channels, or playlists.
    """

    YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.youtube_api_key

    @property
    def source_type(self) -> SourceType:
        return SourceType.YOUTUBE

    async def fetch_new(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Fetch videos from YouTube.

        Config options:
            - query: Search query string
            - channel_id: Specific channel to fetch from
            - playlist_id: Specific playlist to fetch from
            - topics: List of topic strings to search
            - max_results: Maximum number of results (default 10, max 50)
            - order: Sort order (relevance, date, viewCount, rating)
            - video_duration: short, medium, long, any

        Args:
            config: Source configuration
            since: Only fetch videos newer than this

        Returns:
            List of raw content items
        """
        if not self._api_key:
            return []

        videos: list[RawContent] = []

        if config.get("playlist_id"):
            videos = await self._fetch_playlist(config, since)
        elif config.get("channel_id"):
            videos = await self._fetch_channel(config, since)
        else:
            videos = await self._fetch_search(config, since)

        return videos

    async def validate_config(self, config: dict) -> bool:
        """Validate YouTube configuration.

        Requires at least one of: query, channel_id, playlist_id, or topics.
        """
        has_query = bool(config.get("query"))
        has_channel = bool(config.get("channel_id"))
        has_playlist = bool(config.get("playlist_id"))
        has_topics = bool(config.get("topics"))

        return has_query or has_channel or has_playlist or has_topics

    async def _fetch_search(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Search for videos using YouTube search API."""
        query = config.get("query", "")
        topics = config.get("topics", [])

        # Combine query and topics
        search_terms = [query] if query else []
        search_terms.extend(topics)
        search_query = " ".join(search_terms)

        if not search_query:
            return []

        params = {
            "key": self._api_key,
            "part": "snippet",
            "q": search_query,
            "type": "video",
            "maxResults": min(config.get("max_results", 10), 50),
            "order": config.get("order", "relevance"),
            "videoEmbeddable": "true",
            "safeSearch": "moderate",
        }

        # Add duration filter
        if config.get("video_duration"):
            params["videoDuration"] = config["video_duration"]

        # Add date filter
        if since:
            params["publishedAfter"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.YOUTUBE_API_URL}/search",
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        # Get video IDs for additional details
        video_ids = [
            item["id"]["videoId"]
            for item in data.get("items", [])
            if item.get("id", {}).get("videoId")
        ]

        if not video_ids:
            return []

        # Fetch video details for duration and statistics
        return await self._get_video_details(video_ids, data.get("items", []))

    async def _fetch_channel(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Fetch videos from a specific channel."""
        channel_id = config.get("channel_id")
        if not channel_id:
            return []

        params = {
            "key": self._api_key,
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "maxResults": min(config.get("max_results", 10), 50),
            "order": config.get("order", "date"),
        }

        if since:
            params["publishedAfter"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.YOUTUBE_API_URL}/search",
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        video_ids = [
            item["id"]["videoId"]
            for item in data.get("items", [])
            if item.get("id", {}).get("videoId")
        ]

        if not video_ids:
            return []

        return await self._get_video_details(video_ids, data.get("items", []))

    async def _fetch_playlist(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Fetch videos from a specific playlist."""
        playlist_id = config.get("playlist_id")
        if not playlist_id:
            return []

        params = {
            "key": self._api_key,
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": min(config.get("max_results", 10), 50),
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.YOUTUBE_API_URL}/playlistItems",
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        # Extract video IDs from playlist items
        items = data.get("items", [])
        video_ids = [
            item.get("snippet", {}).get("resourceId", {}).get("videoId")
            for item in items
            if item.get("snippet", {}).get("resourceId", {}).get("videoId")
        ]

        if not video_ids:
            return []

        videos = await self._get_video_details(video_ids, items)

        # Filter by date if specified
        if since:
            videos = [v for v in videos if v.published_at and v.published_at > since]

        return videos

    async def _get_video_details(
        self,
        video_ids: list[str],
        search_items: list[dict],
    ) -> list[RawContent]:
        """Get detailed video information."""
        params = {
            "key": self._api_key,
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(video_ids),
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.YOUTUBE_API_URL}/videos",
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        videos: list[RawContent] = []
        for item in data.get("items", []):
            video = self._parse_video(item)
            if video:
                videos.append(video)

        return videos

    def _parse_video(self, item: dict) -> RawContent | None:
        """Parse a video item into RawContent."""
        try:
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            statistics = item.get("statistics", {})

            video_id = item.get("id", "")
            title = snippet.get("title", "")
            description = snippet.get("description", "")
            channel_title = snippet.get("channelTitle", "")

            if not video_id or not title:
                return None

            # Parse published date
            published_at = None
            pub_str = snippet.get("publishedAt")
            if pub_str:
                try:
                    published_at = datetime.fromisoformat(
                        pub_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            # Parse duration (ISO 8601 format, e.g., PT1H2M3S)
            duration = content_details.get("duration", "")
            duration_seconds = self._parse_duration(duration)

            # Build video URL
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            return RawContent(
                source_type=SourceType.YOUTUBE,
                source_url=video_url,
                title=title,
                content=description,
                author=channel_title,
                published_at=published_at,
                metadata={
                    "video_id": video_id,
                    "channel_id": snippet.get("channelId", ""),
                    "channel_title": channel_title,
                    "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "duration_seconds": duration_seconds,
                    "view_count": int(statistics.get("viewCount", 0)),
                    "like_count": int(statistics.get("likeCount", 0)),
                    "comment_count": int(statistics.get("commentCount", 0)),
                    "tags": snippet.get("tags", []),
                    "category_id": snippet.get("categoryId", ""),
                },
            )
        except Exception:
            return None

    def _parse_duration(self, duration: str) -> int:
        """Parse ISO 8601 duration to seconds."""
        if not duration:
            return 0

        import re

        # Pattern for PT#H#M#S format
        pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
        match = re.match(pattern, duration)

        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 3600 + minutes * 60 + seconds


# Factory function
_youtube_adapter: YouTubeAdapter | None = None


def get_youtube_adapter() -> YouTubeAdapter:
    """Get YouTube adapter singleton."""
    global _youtube_adapter
    if _youtube_adapter is None:
        _youtube_adapter = YouTubeAdapter()
    return _youtube_adapter
