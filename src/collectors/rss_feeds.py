"""
rss_feeds.py — Generic RSS/Atom feed collector for blogs and newsletters.

Parses RSS feeds from configured blog and newsletter sources using feedparser.
Filters for articles published within the last 48 hours by default.
Handles broken/unreachable feeds gracefully — one bad feed never blocks the rest.
"""

import feedparser
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.collectors.base import Article
from src.config import RSS_FEEDS, SETTINGS

logger = logging.getLogger(__name__)


def _get_cutoff_time() -> datetime:
    """
    Calculate the cutoff datetime for filtering old articles.

    Returns:
        UTC datetime representing the oldest article we'll accept
    """
    max_age_hours = SETTINGS.get("rss_max_age_hours", 48)
    return datetime.now(tz=timezone.utc) - timedelta(hours=max_age_hours)


def _parse_published_date(entry: dict) -> Optional[datetime]:
    """
    Extract and parse the published date from a feed entry.

    feedparser normalizes dates into 'published_parsed' (a time.struct_time).
    We convert it to a timezone-aware datetime.

    Args:
        entry: A feedparser entry dict

    Returns:
        UTC datetime if parseable, else None
    """
    if entry.get("published_parsed"):
        try:
            t = entry.published_parsed
            return datetime(t[0], t[1], t[2], t[3], t[4], t[5], tzinfo=timezone.utc)
        except Exception:
            pass

    if entry.get("updated_parsed"):
        try:
            t = entry.updated_parsed
            return datetime(t[0], t[1], t[2], t[3], t[4], t[5], tzinfo=timezone.utc)
        except Exception:
            pass

    return None


def _clean_html(text: str) -> str:
    """
    Strip HTML tags from a string and collapse whitespace.

    Args:
        text: Raw HTML or plain text string

    Returns:
        Clean plain text, max 500 chars
    """
    clean = re.sub(r"<[^>]+>", "", text or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:500]


def _extract_source_name(feed: feedparser.FeedParserDict, url: str) -> str:
    """
    Get a human-readable source name from the feed metadata or URL.

    Args:
        feed: Parsed feedparser object
        url: Original feed URL (used as fallback)

    Returns:
        Source name string
    """
    if feed.feed.get("title"):
        return feed.feed.title.strip()[:60]

    # Fall back to domain name extracted from URL
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.replace("www.", "")
        return domain
    except Exception:
        return "RSS Feed"


def _parse_single_feed(url: str, topic: str, cutoff: datetime) -> list[Article]:
    """
    Parse a single RSS/Atom feed URL and return Article objects.

    Filters out articles older than the cutoff time.
    Handles any parsing errors gracefully.

    Args:
        url: RSS feed URL
        topic: Topic category for all articles from this feed
        cutoff: Oldest acceptable published datetime (UTC)

    Returns:
        List of Article objects from this feed
    """
    articles: list[Article] = []

    try:
        feed = feedparser.parse(
            url,
            request_headers={
                "User-Agent": "pdd-agent/1.0",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
            }
        )

        # Check for hard failures
        if feed.bozo and not feed.entries:
            logger.warning(f"RSS: bad/empty feed at {url[:80]} — {feed.bozo_exception}")
            return []

        source_name = _extract_source_name(feed, url)

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                continue

            # Date filtering — only include recent articles
            pub_dt = _parse_published_date(entry)
            if pub_dt and pub_dt < cutoff:
                continue  # Too old, skip

            published_at = pub_dt.isoformat() if pub_dt else None

            # Build summary from description or content
            summary_raw = (
                entry.get("summary", "")
                or entry.get("description", "")
                or (entry.get("content", [{}])[0].get("value", "") if entry.get("content") else "")
            )
            summary = _clean_html(summary_raw)

            articles.append(Article(
                title=title,
                url=link,
                source_name=source_name,
                source_type="rss",
                topic=topic,
                summary=summary,
                published_at=published_at,
            ))

        logger.debug(f"RSS [{topic}] {source_name}: {len(articles)} articles from {url[:60]}")

    except Exception as e:
        logger.warning(f"RSS: unexpected error parsing {url[:80]}: {e}")

    return articles


def collect_rss_feeds() -> list[Article]:
    """
    Collect articles from all configured RSS feeds for all topics.

    Processes each feed independently — failures are logged as warnings and
    the rest of the feeds continue processing uninterrupted.

    Returns:
        List of Article objects across all topics and feeds
    """
    all_articles: list[Article] = []
    cutoff = _get_cutoff_time()

    logger.info(f"RSS: collecting feeds (cutoff: articles newer than {cutoff.strftime('%Y-%m-%d %H:%M UTC')})")

    for topic, feed_urls in RSS_FEEDS.items():
        topic_articles: list[Article] = []

        for url in feed_urls:
            feed_articles = _parse_single_feed(url, topic, cutoff)
            topic_articles.extend(feed_articles)

        logger.info(f"RSS [{topic}]: {len(topic_articles)} total articles from {len(feed_urls)} feeds")
        all_articles.extend(topic_articles)

    return all_articles


# ─────────────────────────────────────────────
# Standalone test — run with: python src/collectors/rss_feeds.py
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("Testing RSS feeds collector...")
    articles = collect_rss_feeds()
    print(f"\nTotal articles collected: {len(articles)}")
    print("\nFirst 3 articles:")
    for a in articles[:3]:
        print(f"  [{a.topic}] {a.title[:80]}")
        print(f"    Source: {a.source_name} | Published: {a.published_at}")
        print(f"    URL: {a.url[:80]}")
