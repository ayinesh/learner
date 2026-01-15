"""RSS Adapter - Fetches content from RSS/Atom feeds."""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from src.modules.content.interface import RawContent, SourceAdapter
from src.shared.models import SourceType


class RSSAdapter(SourceAdapter):
    """Adapter for fetching content from RSS/Atom feeds.

    Supports both RSS 2.0 and Atom feed formats for blogs,
    newsletters, and other syndicated content.
    """

    # Common namespaces
    ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
    DC_NS = {"dc": "http://purl.org/dc/elements/1.1/"}
    CONTENT_NS = {"content": "http://purl.org/rss/1.0/modules/content/"}

    @property
    def source_type(self) -> SourceType:
        return SourceType.BLOG

    async def fetch_new(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Fetch items from RSS/Atom feeds.

        Config options:
            - feed_urls: list of RSS/Atom feed URLs
            - max_items: maximum items per feed (default 10)
            - source_type: override source type (default BLOG)

        Args:
            config: Source configuration
            since: Only fetch items newer than this

        Returns:
            List of raw content items
        """
        feed_urls = config.get("feed_urls", [])
        max_items = config.get("max_items", 10)
        override_source = config.get("source_type")

        all_items: list[RawContent] = []

        async with httpx.AsyncClient() as client:
            for url in feed_urls:
                try:
                    response = await client.get(
                        url,
                        timeout=30.0,
                        follow_redirects=True,
                        headers={"User-Agent": "LearningSystemBot/1.0"},
                    )
                    response.raise_for_status()

                    items = self._parse_feed(
                        response.text,
                        url,
                        override_source,
                    )

                    # Filter by date
                    if since:
                        items = [i for i in items if i.published_at and i.published_at > since]

                    # Limit items per feed
                    items = items[:max_items]
                    all_items.extend(items)

                except Exception:
                    # Skip failed feeds
                    continue

        return all_items

    async def validate_config(self, config: dict) -> bool:
        """Validate RSS configuration.

        Requires at least one feed URL.
        """
        feed_urls = config.get("feed_urls", [])
        return len(feed_urls) > 0

    def _parse_feed(
        self,
        content: str,
        feed_url: str,
        override_source: str | None,
    ) -> list[RawContent]:
        """Parse RSS or Atom feed content."""
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return []

        # Detect feed type
        if root.tag == "rss" or root.find("channel") is not None:
            return self._parse_rss(root, feed_url, override_source)
        elif "feed" in root.tag.lower() or root.find("atom:entry", self.ATOM_NS) is not None:
            return self._parse_atom(root, feed_url, override_source)
        else:
            return []

    def _parse_rss(
        self,
        root: ET.Element,
        feed_url: str,
        override_source: str | None,
    ) -> list[RawContent]:
        """Parse RSS 2.0 feed."""
        items = []
        channel = root.find("channel")
        if channel is None:
            return items

        # Get channel info for defaults
        channel_title = channel.find("title")
        default_author = channel_title.text if channel_title is not None else ""

        for item in channel.findall("item"):
            try:
                content_item = self._parse_rss_item(
                    item,
                    feed_url,
                    default_author,
                    override_source,
                )
                if content_item:
                    items.append(content_item)
            except Exception:
                continue

        return items

    def _parse_rss_item(
        self,
        item: ET.Element,
        feed_url: str,
        default_author: str,
        override_source: str | None,
    ) -> RawContent | None:
        """Parse a single RSS item."""
        # Title
        title_elem = item.find("title")
        if title_elem is None or not title_elem.text:
            return None
        title = self._clean_html(title_elem.text)

        # Content - try content:encoded first, then description
        content = ""
        content_encoded = item.find("content:encoded", self.CONTENT_NS)
        if content_encoded is not None and content_encoded.text:
            content = self._clean_html(content_encoded.text)
        else:
            description = item.find("description")
            if description is not None and description.text:
                content = self._clean_html(description.text)

        # Link
        link_elem = item.find("link")
        url = link_elem.text if link_elem is not None and link_elem.text else feed_url

        # Author
        author = default_author
        author_elem = item.find("author")
        if author_elem is not None and author_elem.text:
            author = author_elem.text
        else:
            dc_creator = item.find("dc:creator", self.DC_NS)
            if dc_creator is not None and dc_creator.text:
                author = dc_creator.text

        # Publication date
        published_at = None
        pub_date = item.find("pubDate")
        if pub_date is not None and pub_date.text:
            try:
                published_at = parsedate_to_datetime(pub_date.text)
            except Exception:
                pass

        # Categories/tags
        categories = []
        for cat in item.findall("category"):
            if cat.text:
                categories.append(cat.text)

        # Determine source type
        source_type = SourceType.BLOG
        if override_source:
            try:
                source_type = SourceType(override_source)
            except ValueError:
                pass

        return RawContent(
            source_type=source_type,
            source_url=url,
            title=title,
            content=content,
            author=author,
            published_at=published_at,
            metadata={
                "feed_url": feed_url,
                "categories": categories,
            },
        )

    def _parse_atom(
        self,
        root: ET.Element,
        feed_url: str,
        override_source: str | None,
    ) -> list[RawContent]:
        """Parse Atom feed."""
        items = []

        # Handle namespace in root tag
        ns = self.ATOM_NS
        if root.tag.startswith("{"):
            # Extract namespace from tag
            actual_ns = root.tag[1:root.tag.index("}")]
            ns = {"atom": actual_ns}

        # Get feed info for defaults
        feed_title = root.find("atom:title", ns)
        default_author = feed_title.text if feed_title is not None else ""

        for entry in root.findall("atom:entry", ns):
            try:
                content_item = self._parse_atom_entry(
                    entry,
                    feed_url,
                    default_author,
                    override_source,
                    ns,
                )
                if content_item:
                    items.append(content_item)
            except Exception:
                continue

        return items

    def _parse_atom_entry(
        self,
        entry: ET.Element,
        feed_url: str,
        default_author: str,
        override_source: str | None,
        ns: dict,
    ) -> RawContent | None:
        """Parse a single Atom entry."""
        # Title
        title_elem = entry.find("atom:title", ns)
        if title_elem is None or not title_elem.text:
            return None
        title = self._clean_html(title_elem.text)

        # Content
        content = ""
        content_elem = entry.find("atom:content", ns)
        if content_elem is not None and content_elem.text:
            content = self._clean_html(content_elem.text)
        else:
            summary_elem = entry.find("atom:summary", ns)
            if summary_elem is not None and summary_elem.text:
                content = self._clean_html(summary_elem.text)

        # Link
        url = feed_url
        for link in entry.findall("atom:link", ns):
            rel = link.get("rel", "alternate")
            if rel == "alternate" and link.get("href"):
                url = link.get("href")
                break

        # Author
        author = default_author
        author_elem = entry.find("atom:author", ns)
        if author_elem is not None:
            name_elem = author_elem.find("atom:name", ns)
            if name_elem is not None and name_elem.text:
                author = name_elem.text

        # Publication date
        published_at = None
        published_elem = entry.find("atom:published", ns)
        if published_elem is None:
            published_elem = entry.find("atom:updated", ns)
        if published_elem is not None and published_elem.text:
            try:
                published_at = datetime.fromisoformat(
                    published_elem.text.replace("Z", "+00:00")
                )
            except ValueError:
                pass

        # Categories
        categories = []
        for cat in entry.findall("atom:category", ns):
            term = cat.get("term")
            if term:
                categories.append(term)

        # Determine source type
        source_type = SourceType.BLOG
        if override_source:
            try:
                source_type = SourceType(override_source)
            except ValueError:
                pass

        return RawContent(
            source_type=source_type,
            source_url=url,
            title=title,
            content=content,
            author=author,
            published_at=published_at,
            metadata={
                "feed_url": feed_url,
                "categories": categories,
            },
        )

    def _clean_html(self, text: str) -> str:
        """Strip HTML tags and clean whitespace."""
        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", " ", text)
        # Decode common entities
        clean = clean.replace("&nbsp;", " ")
        clean = clean.replace("&amp;", "&")
        clean = clean.replace("&lt;", "<")
        clean = clean.replace("&gt;", ">")
        clean = clean.replace("&quot;", '"')
        clean = clean.replace("&#39;", "'")
        # Normalize whitespace
        clean = " ".join(clean.split())
        return clean.strip()


# Factory function
_rss_adapter: RSSAdapter | None = None


def get_rss_adapter() -> RSSAdapter:
    """Get RSS adapter singleton."""
    global _rss_adapter
    if _rss_adapter is None:
        _rss_adapter = RSSAdapter()
    return _rss_adapter
