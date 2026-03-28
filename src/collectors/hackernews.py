"""
hackernews.py — Hacker News API collector.

Uses the public HN Firebase REST API (no authentication required).
Fetches top stories, filters by keyword relevance and minimum score.
"""
from __future__ import annotations  # enables X | Y union syntax on Python 3.9

import requests
import logging
from typing import Optional, Union

from src.collectors.base import Article
from src.config import HACKERNEWS_CONFIG, SETTINGS

logger = logging.getLogger(__name__)


def _fetch_json(url: str, timeout: int = None) -> Optional[Union[dict, list]]:
    """
    Fetch and parse JSON from a URL.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Parsed JSON data, or None if the request failed
    """
    timeout = timeout or SETTINGS["request_timeout"]
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.warning(f"HackerNews: failed to fetch {url[:80]}: {e}")
        return None


def _is_relevant(title: str) -> bool:
    """
    Check if a story title contains any of the configured relevant keywords.

    Case-insensitive match against the keyword list in HACKERNEWS_CONFIG.

    Args:
        title: The story title to check

    Returns:
        True if the story is relevant to our digest topics
    """
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in HACKERNEWS_CONFIG["relevant_keywords"])


def _assign_topic(title: str) -> str:
    """
    Assign the best-matching topic to a HN story based on its title.

    This is a simple keyword-based classifier — good enough for our purposes.

    Args:
        title: The story title

    Returns:
        Topic string matching one of the VALID_TOPICS in config
    """
    title_lower = title.lower()

    # Check in priority order — most specific first
    india_keywords = ["india", "indian", "bengaluru", "mumbai", "delhi", "rupee", "startup india"]
    if any(kw in title_lower for kw in india_keywords):
        return "india"

    ai_tools_keywords = ["claude", "anthropic", "chatgpt", "openai", "cursor", "figma ai",
                          "gpt-4", "gpt-5", "copilot", "gemini", "fireflies"]
    if any(kw in title_lower for kw in ai_tools_keywords):
        return "ai_tools"

    pm_keywords = ["product manager", "product management", "product roadmap", "pm ", "feature flag"]
    if any(kw in title_lower for kw in pm_keywords):
        return "product_management"

    creator_keywords = ["instagram", "tiktok", "youtube", "linkedin", "content creator",
                        "social media", "influencer", "newsletter"]
    if any(kw in title_lower for kw in creator_keywords):
        return "content_creators"

    # Default to ai_policy for everything else AI/ML/tech-related
    return "ai_policy"


def _fetch_story(story_id: int) -> Optional[Article]:
    """
    Fetch a single HN story by ID and convert to Article.

    Args:
        story_id: The Hacker News item ID

    Returns:
        Article object if the story is relevant and above score threshold, else None
    """
    item_url = HACKERNEWS_CONFIG["item_url"].format(id=story_id)
    item = _fetch_json(item_url)

    if not item or item.get("type") != "story":
        return None

    title = item.get("title", "").strip()
    url = item.get("url", f"https://news.ycombinator.com/item?id={story_id}").strip()
    score = item.get("score", 0)
    comment_count = item.get("descendants", 0)

    # Quality and relevance filters
    if score < HACKERNEWS_CONFIG["min_score"]:
        return None
    if not _is_relevant(title):
        return None

    # HN stories don't have structured publish times in the API,
    # but 'time' is a Unix timestamp
    published_at: Optional[str] = None
    if item.get("time"):
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(item["time"], tz=timezone.utc)
        published_at = dt.isoformat()

    topic = _assign_topic(title)

    # Use first few words of text as summary if it's a "Ask HN" / "Show HN" post
    text = item.get("text", "")
    if text:
        import re
        summary = re.sub(r"<[^>]+>", "", text).strip()[:300]
    else:
        summary = f"HN score: {score} | {comment_count} comments"

    return Article(
        title=title,
        url=url,
        source_name="Hacker News",
        source_type="hackernews",
        topic=topic,
        summary=summary,
        published_at=published_at,
        score=score,
        comment_count=comment_count,
    )


def collect_hackernews() -> list[Article]:
    """
    Collect relevant stories from Hacker News top stories.

    Fetches the top N story IDs, then retrieves each story in sequence,
    filtering by keyword relevance and minimum score threshold.

    Returns:
        List of Article objects for relevant top stories
    """
    # Fetch top story IDs
    story_ids = _fetch_json(HACKERNEWS_CONFIG["top_stories_url"])
    if not story_ids:
        logger.error("HackerNews: could not fetch top story IDs")
        return []

    max_stories = HACKERNEWS_CONFIG["max_stories"]
    story_ids = story_ids[:max_stories]

    articles: list[Article] = []
    for story_id in story_ids:
        article = _fetch_story(story_id)
        if article:
            articles.append(article)

    logger.info(f"HackerNews: {len(articles)} relevant stories from top {max_stories}")
    return articles


# ─────────────────────────────────────────────
# Standalone test — run with: python src/collectors/hackernews.py
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("Testing Hacker News collector...")
    articles = collect_hackernews()
    print(f"\nTotal articles collected: {len(articles)}")
    print("\nFirst 3 articles:")
    for a in articles[:3]:
        print(f"  [{a.topic}] {a.title[:80]}")
        print(f"    Score: {a.score} | Comments: {a.comment_count}")
        print(f"    URL: {a.url[:80]}")
