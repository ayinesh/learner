"""arXiv Adapter - Fetches papers from arXiv API."""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from src.modules.content.interface import RawContent, SourceAdapter
from src.shared.models import SourceType


class ArxivAdapter(SourceAdapter):
    """Adapter for fetching papers from arXiv.

    Uses the arXiv API to search and retrieve papers based on
    categories, authors, or keywords.
    """

    ARXIV_API_URL = "http://export.arxiv.org/api/query"
    NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}

    @property
    def source_type(self) -> SourceType:
        return SourceType.ARXIV

    async def fetch_new(
        self,
        config: dict,
        since: datetime | None = None,
    ) -> list[RawContent]:
        """Fetch papers from arXiv.

        Config options:
            - categories: list of arXiv categories (e.g., ["cs.AI", "cs.LG"])
            - keywords: list of search keywords
            - authors: list of author names
            - max_results: maximum number of results (default 10)

        Args:
            config: Source configuration
            since: Only fetch papers newer than this

        Returns:
            List of raw content items
        """
        query = self._build_query(config)
        max_results = config.get("max_results", 10)

        # Build request URL
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.ARXIV_API_URL,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()

        # Parse XML response
        papers = self._parse_response(response.text)

        # Filter by date if specified
        if since:
            papers = [p for p in papers if p.published_at and p.published_at > since]

        return papers

    async def validate_config(self, config: dict) -> bool:
        """Validate arXiv configuration.

        Requires at least one of: categories, keywords, or authors.
        """
        has_categories = bool(config.get("categories"))
        has_keywords = bool(config.get("keywords"))
        has_authors = bool(config.get("authors"))

        return has_categories or has_keywords or has_authors

    def _build_query(self, config: dict) -> str:
        """Build arXiv query string from config."""
        query_parts = []

        # Category filters
        categories = config.get("categories", [])
        if categories:
            cat_query = " OR ".join(f"cat:{cat}" for cat in categories)
            query_parts.append(f"({cat_query})")

        # Keyword search
        keywords = config.get("keywords", [])
        if keywords:
            kw_query = " OR ".join(f'all:"{kw}"' for kw in keywords)
            query_parts.append(f"({kw_query})")

        # Author search
        authors = config.get("authors", [])
        if authors:
            auth_query = " OR ".join(f'au:"{author}"' for author in authors)
            query_parts.append(f"({auth_query})")

        # Combine with AND
        return " AND ".join(query_parts) if query_parts else "all:*"

    def _parse_response(self, xml_content: str) -> list[RawContent]:
        """Parse arXiv XML response into RawContent items."""
        root = ET.fromstring(xml_content)
        papers = []

        for entry in root.findall("atom:entry", self.NAMESPACE):
            try:
                paper = self._parse_entry(entry)
                if paper:
                    papers.append(paper)
            except Exception:
                # Skip malformed entries
                continue

        return papers

    def _parse_entry(self, entry: ET.Element) -> RawContent | None:
        """Parse a single arXiv entry."""
        # Extract title
        title_elem = entry.find("atom:title", self.NAMESPACE)
        if title_elem is None or not title_elem.text:
            return None
        title = self._clean_text(title_elem.text)

        # Extract abstract/summary
        summary_elem = entry.find("atom:summary", self.NAMESPACE)
        content = self._clean_text(summary_elem.text) if summary_elem is not None and summary_elem.text else ""

        # Extract authors
        authors = []
        for author in entry.findall("atom:author", self.NAMESPACE):
            name_elem = author.find("atom:name", self.NAMESPACE)
            if name_elem is not None and name_elem.text:
                authors.append(name_elem.text)
        author_str = ", ".join(authors)

        # Extract URL (use abs link)
        url = ""
        for link in entry.findall("atom:link", self.NAMESPACE):
            if link.get("type") == "text/html":
                url = link.get("href", "")
                break
        if not url:
            # Fallback to id
            id_elem = entry.find("atom:id", self.NAMESPACE)
            url = id_elem.text if id_elem is not None and id_elem.text else ""

        # Extract publication date
        published_elem = entry.find("atom:published", self.NAMESPACE)
        published_at = None
        if published_elem is not None and published_elem.text:
            try:
                published_at = datetime.fromisoformat(
                    published_elem.text.replace("Z", "+00:00")
                )
            except ValueError:
                pass

        # Extract categories
        categories = []
        for category in entry.findall("atom:category", self.NAMESPACE):
            term = category.get("term")
            if term:
                categories.append(term)

        # Extract arXiv ID
        arxiv_id = ""
        id_elem = entry.find("atom:id", self.NAMESPACE)
        if id_elem is not None and id_elem.text:
            # ID format: http://arxiv.org/abs/XXXX.XXXXX
            match = re.search(r"abs/(.+)$", id_elem.text)
            if match:
                arxiv_id = match.group(1)

        return RawContent(
            source_type=SourceType.ARXIV,
            source_url=url,
            title=title,
            content=content,
            author=author_str,
            published_at=published_at,
            metadata={
                "arxiv_id": arxiv_id,
                "categories": categories,
                "pdf_url": url.replace("/abs/", "/pdf/") if "/abs/" in url else "",
            },
        )

    def _clean_text(self, text: str) -> str:
        """Clean arXiv text (remove extra whitespace)."""
        return " ".join(text.split())


# Factory function
_arxiv_adapter: ArxivAdapter | None = None


def get_arxiv_adapter() -> ArxivAdapter:
    """Get arXiv adapter singleton."""
    global _arxiv_adapter
    if _arxiv_adapter is None:
        _arxiv_adapter = ArxivAdapter()
    return _arxiv_adapter
