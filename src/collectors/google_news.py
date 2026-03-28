"""
google_news.py — Google News RSS collector.

Fetches news articles via Google News RSS feeds (no API key required).
Constructs query URLs from config and parses with feedparser.
"""

import feedparser
import logging
from datetime import datetime, timezone
from typing import Optional

from src.collectors.base import Article
from src.config import GOOGLE_NEWS_QUERIES, SETTINGS

logger = logging.getLogger(__name__)

# Base URL pattern for Google News RSS search
GOOGLE_NEWS_BASE_URL = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"


def _build_query_url(query: str) -> str:
    """
    Build a Google News RSS URL for a given search query.

    Args:
        query: Search string (e.g., "AI policy regulation 2025")

    Returns:
        Full RSS URL ready for feedparser
    """
    import urllib.parse
    encoded = urllib.parse.quote(query)
    return GOOGLE_NEWS_BASE_URL.format(query=encoded)


def _parse_feed(url: str, topic: str) -> list[Article]:
    """
    Parse a single Google News RSS feed URL and return Article objects.

    Args:
        url: The full RSS URL to fetch and parse
        topic: The topic category for these articles

    Returns:
        List of Article objects from this feed
    """
    articles: list[Article] = []

    try:
        feed = feedparser.parse(url, request_headers={"User-Agent": "pdd-agent/1.0"})

        if feed.bozo and not feed.entries:
            # bozo=True means feedparser encountered a malformed feed
            logger.warning(f"Google News: malformed/empty feed for URL: {url[:80]}...")
            return []

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                continue

            # Extract summary — Google News wraps it in HTML; grab plain text
            summary_raw = entry.get("summary", "")
            # Strip basic HTML tags from the summary
            import re
            summary = re.sub(r"<[^>]+>", "", summary_raw).strip()[:500]

            # Parse published date
            published_at: Optional[str] = None
            if entry.get("published_parsed"):
                try:
                    dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    published_at = dt.isoformat()
                except Exception:
                    pass

            articles.append(Article(
                title=title,
                url=link,
                source_name="Google News",
                source_type="google_news",
                topic=topic,
                summary=summary,
                published_at=published_at,
            ))

    except Exception as e:
        logger.warning(f"Google News: error parsing feed {url[:80]}: {e}")

    return articles


def collect_google_news() -> list[Article]:
    """
    Collect articles from Google News RSS for all configured topics and queries.

    Deduplicates by URL within each topic so the same article from different
    queries only appears once.

    Returns:
        List of Article objects across all topics
    """
    all_articles: list[Article] = []
    seen_urls_by_topic: dict[str, set[str]] = {topic: set() for topic in GOOGLE_NEWS_QUERIES}

    for topic, queries in GOOGLE_NEWS_QUERIES.items():
        topic_count = 0
        for query in queries:
            url = _build_query_url(query)
            articles = _parse_feed(url, topic)

            for article in articles:
                if article.url not in seen_urls_by_topic[topic]:
                    seen_urls_by_topic[topic].add(article.url)
                    all_articles.append(article)
                    topic_count += 1

        logger.info(f"Google News [{topic}]: {topic_count} unique articles from {len(queries)} queries")

    return all_articles


# ─────────────────────────────────────────────
# Standalone test — run with: python src/collectors/google_news.py
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("Testing Google News collector...")
    articles = collect_google_news()
    print(f"\nTotal articles collected: {len(articles)}")
    print("\nFirst 3 articles:")
    for a in articles[:3]:
        print(f"  [{a.topic}] {a.title[:80]}")
        print(f"    Source: {a.source_name} | Published: {a.published_at}")
        print(f"    URL: {a.url[:80]}")
