"""
reddit_collector.py — Reddit API collector using PRAW.

Fetches top posts from configured subreddits over the last 24 hours.
Requires REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET environment variables.
If credentials are missing, skips Reddit collection entirely with a warning.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional

from src.collectors.base import Article
from src.config import REDDIT_SUBREDDITS, SETTINGS

logger = logging.getLogger(__name__)

# Reddit API credentials from environment variables
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = "pdd-agent/1.0 (Personal Daily Digest; automated)"

# How many posts to fetch per subreddit
POSTS_PER_SUBREDDIT = 10


def _get_reddit_client():
    """
    Initialize and return a PRAW Reddit client.

    Uses read-only mode since we only need to read posts, not write.

    Returns:
        praw.Reddit instance, or None if credentials are unavailable
    """
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        logger.warning(
            "Reddit: REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET not set. "
            "Skipping Reddit collection. (This is fine for local testing.)"
        )
        return None

    try:
        import praw
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
        # Test the connection by accessing the read-only property
        _ = reddit.read_only
        logger.info("Reddit: client initialized successfully")
        return reddit
    except ImportError:
        logger.error("Reddit: praw package not installed. Run: pip install praw")
        return None
    except Exception as e:
        logger.error(f"Reddit: failed to initialize client: {e}")
        return None


def _fetch_subreddit_top(reddit, subreddit_name: str, topic: str) -> list[Article]:
    """
    Fetch top posts from a single subreddit for the past day.

    Args:
        reddit: PRAW Reddit client
        subreddit_name: Name of the subreddit (without r/ prefix)
        topic: Topic category to assign to all posts from this subreddit

    Returns:
        List of Article objects from the subreddit's top posts
    """
    articles: list[Article] = []

    try:
        subreddit = reddit.subreddit(subreddit_name)
        top_posts = subreddit.top(time_filter="day", limit=POSTS_PER_SUBREDDIT)

        for post in top_posts:
            # Skip stickied announcements and deleted posts
            if post.stickied or post.removed_by_category:
                continue

            title = post.title.strip()
            url = post.url.strip()

            # For self posts (text posts), use the post's Reddit URL instead of the external URL
            if post.is_self:
                url = f"https://www.reddit.com{post.permalink}"

            # Build summary from selftext (first 200 chars) or link description
            if post.selftext:
                summary = post.selftext.strip()[:200]
                if len(post.selftext) > 200:
                    summary += "..."
            else:
                summary = f"r/{subreddit_name} | {post.score} upvotes | {post.num_comments} comments"

            # Convert Unix timestamp to ISO string
            published_at: Optional[str] = None
            if post.created_utc:
                dt = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
                published_at = dt.isoformat()

            articles.append(Article(
                title=title,
                url=url,
                source_name=f"Reddit r/{subreddit_name}",
                source_type="reddit",
                topic=topic,
                summary=summary,
                published_at=published_at,
                score=post.score,
                comment_count=post.num_comments,
            ))

        logger.debug(f"Reddit r/{subreddit_name}: {len(articles)} posts collected")

    except Exception as e:
        # Subreddit might be private, quarantined, or banned — log and continue
        logger.warning(f"Reddit r/{subreddit_name}: failed to fetch posts: {e}")

    return articles


def collect_reddit() -> list[Article]:
    """
    Collect top posts from all configured subreddits.

    Skips entirely if Reddit API credentials are not set in environment variables.
    Individual subreddit failures are logged and skipped — won't crash the pipeline.

    Returns:
        List of Article objects from Reddit, or empty list if credentials missing
    """
    reddit = _get_reddit_client()
    if reddit is None:
        return []

    all_articles: list[Article] = []

    for topic, subreddits in REDDIT_SUBREDDITS.items():
        topic_count = 0
        for subreddit_name in subreddits:
            articles = _fetch_subreddit_top(reddit, subreddit_name, topic)
            all_articles.extend(articles)
            topic_count += len(articles)

        logger.info(f"Reddit [{topic}]: {topic_count} posts from {len(subreddits)} subreddits")

    return all_articles


# ─────────────────────────────────────────────
# Standalone test — run with: python src/collectors/reddit_collector.py
# Requires REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in your environment
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not REDDIT_CLIENT_ID:
        print("No REDDIT_CLIENT_ID found — skipping (set env vars to test Reddit)")
    else:
        print("Testing Reddit collector...")
        articles = collect_reddit()
        print(f"\nTotal posts collected: {len(articles)}")
        print("\nFirst 3 posts:")
        for a in articles[:3]:
            print(f"  [{a.topic}] {a.title[:80]}")
            print(f"    Source: {a.source_name} | Score: {a.score} | Comments: {a.comment_count}")
