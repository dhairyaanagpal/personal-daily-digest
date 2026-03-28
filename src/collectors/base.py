"""
base.py — Shared Article dataclass and collector utilities.

Every collector must output a list of Article objects with this schema.
This ensures a consistent data contract between collectors and the synthesizer.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class Article:
    """
    Represents a single news article or post collected from any source.

    All collectors must return List[Article] — this is the universal data contract.
    """
    title: str
    url: str
    source_name: str    # e.g., "Google News", "Reddit r/artificial", "Anthropic Blog"
    source_type: str    # "google_news", "reddit", "rss", "hackernews"
    topic: str          # "ai_policy", "product_management", "ai_tools", "india", "content_creators"
    summary: str = ""   # short description if available from the source
    published_at: Optional[str] = None  # ISO format datetime string
    score: Optional[int] = None         # Reddit upvotes or HN points, if applicable
    comment_count: Optional[int] = None  # for Reddit/HN

    def to_dict(self) -> dict:
        """Convert article to a plain dictionary for JSON serialization."""
        return asdict(self)

    def __repr__(self) -> str:
        return f"Article(title={self.title[:60]!r}, source={self.source_name!r}, topic={self.topic!r})"


def collect_safely(collector_fn, name: str) -> list[Article]:
    """
    Wrap any collector function so a single source failure never crashes the pipeline.

    Args:
        collector_fn: A callable that returns List[Article]
        name: Human-readable name for the collector (used in log messages)

    Returns:
        List of articles, or empty list if the collector raised any exception.
    """
    try:
        articles = collector_fn()
        logger.info(f"{name}: collected {len(articles)} articles")
        return articles
    except Exception as e:
        logger.error(f"{name} failed: {e}", exc_info=True)
        return []


def deduplicate_by_url(articles: list[Article]) -> list[Article]:
    """
    Remove duplicate articles by exact URL match.

    Keeps the first occurrence when duplicates are found (preserves original ordering).

    Args:
        articles: List of articles, potentially with duplicate URLs

    Returns:
        Deduplicated list of articles
    """
    seen_urls: set[str] = set()
    unique: list[Article] = []

    for article in articles:
        # Normalize URL slightly: strip trailing slashes and query params that are tracking-only
        normalized_url = article.url.rstrip("/")
        if normalized_url not in seen_urls:
            seen_urls.add(normalized_url)
            unique.append(article)

    removed = len(articles) - len(unique)
    if removed > 0:
        logger.info(f"Deduplication: removed {removed} duplicate articles (by URL)")

    return unique


def deduplicate_by_title_similarity(articles: list[Article]) -> list[Article]:
    """
    Remove articles with highly similar titles (same story from multiple sources).

    Uses a simple word-overlap heuristic: if two titles share >70% of meaningful words,
    keep the one with higher score (or the more recent one if scores are equal).

    Args:
        articles: List of articles, URL-deduplicated

    Returns:
        Further deduplicated list
    """
    # Common English stop words to ignore in title comparison
    STOP_WORDS = {
        "the", "a", "an", "is", "in", "on", "at", "to", "for", "of", "and",
        "or", "but", "with", "from", "by", "as", "it", "its", "this", "that",
        "are", "was", "were", "be", "been", "has", "have", "had", "will",
        "would", "could", "should", "new", "says", "said",
    }

    def meaningful_words(title: str) -> set[str]:
        words = title.lower().split()
        return {w.strip(".,!?;:'\"()[]") for w in words if w not in STOP_WORDS and len(w) >= 2}

    def similarity(a: str, b: str) -> float:
        words_a = meaningful_words(a)
        words_b = meaningful_words(b)
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)  # Jaccard similarity

    kept: list[Article] = []
    for article in articles:
        is_duplicate = False
        for i, existing in enumerate(kept):
            if article.topic == existing.topic:  # only compare within same topic
                sim = similarity(article.title, existing.title)
                if sim > 0.50:
                    # Keep the one with higher score or more recent date
                    article_score = article.score or 0
                    existing_score = existing.score or 0
                    if article_score > existing_score:
                        kept[i] = article  # replace with higher-scored version
                    is_duplicate = True
                    break
        if not is_duplicate:
            kept.append(article)

    removed = len(articles) - len(kept)
    if removed > 0:
        logger.info(f"Title similarity dedup: removed {removed} near-duplicate articles")

    return kept


def trim_articles_per_section(
    articles: list[Article],
    max_per_section: int = 10,
) -> list[Article]:
    """
    Trim to the top N articles per topic section, sorted by score then recency.

    This is the final step before sending articles to Gemini, to keep the prompt
    within a reasonable token budget.

    Args:
        articles: Full deduplicated article list
        max_per_section: Maximum articles to keep per topic

    Returns:
        Trimmed list with at most max_per_section articles per topic
    """
    from collections import defaultdict

    by_topic: dict[str, list[Article]] = defaultdict(list)
    for article in articles:
        by_topic[article.topic].append(article)

    trimmed: list[Article] = []
    for topic, topic_articles in by_topic.items():
        # Sort by score descending, then by published_at descending (most recent first)
        def sort_key(a: Article):
            score = a.score or 0
            # Parse date for secondary sort; default to epoch if missing
            try:
                from dateutil import parser as dateparser
                dt = dateparser.parse(a.published_at) if a.published_at else datetime.min
                # Make timezone-naive for comparison
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
            except Exception:
                dt = datetime.min
            return (score, dt)

        sorted_articles = sorted(topic_articles, key=sort_key, reverse=True)
        trimmed.extend(sorted_articles[:max_per_section])
        logger.debug(f"Topic '{topic}': kept {min(len(topic_articles), max_per_section)} of {len(topic_articles)} articles")

    return trimmed
