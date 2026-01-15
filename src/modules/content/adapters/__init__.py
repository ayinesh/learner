"""Content Adapters - Source-specific content fetchers."""

from src.modules.content.adapters.arxiv import ArxivAdapter, get_arxiv_adapter
from src.modules.content.adapters.rss import RSSAdapter, get_rss_adapter
from src.modules.content.adapters.youtube import YouTubeAdapter, get_youtube_adapter
from src.modules.content.adapters.github import GitHubAdapter, get_github_adapter
from src.modules.content.adapters.reddit import RedditAdapter, get_reddit_adapter
from src.modules.content.adapters.twitter import TwitterAdapter, get_twitter_adapter

__all__ = [
    "ArxivAdapter",
    "RSSAdapter",
    "YouTubeAdapter",
    "GitHubAdapter",
    "RedditAdapter",
    "TwitterAdapter",
    "get_arxiv_adapter",
    "get_rss_adapter",
    "get_youtube_adapter",
    "get_github_adapter",
    "get_reddit_adapter",
    "get_twitter_adapter",
]
