"""
main.py — PDD Agent orchestrator.

Entry point for the full pipeline:
  1. Determine edition type (weekday / weekend / skip Sunday)
  2. Collect articles from all 4 sources
  3. Deduplicate and trim
  4. Send to Gemini for synthesis
  5. Generate HTML
  6. Archive management

Run with:
  python src/main.py              # full live run
  DRY_RUN=true python src/main.py # use sample data, skip Gemini
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure the project root is on sys.path so `src.*` imports work
# whether the script is run as `python src/main.py` or `python -m src.main`
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ─── Logging setup (must happen before any imports that use logger) ────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("pdd.main")

# ─── Import pipeline components ───────────────────────────────────────────────
from src.collectors.base import (
    Article,
    collect_safely,
    deduplicate_by_url,
    deduplicate_by_title_similarity,
    trim_articles_per_section,
)
from src.collectors.google_news import collect_google_news
from src.collectors.hackernews import collect_hackernews
from src.collectors.rss_feeds import collect_rss_feeds
from src.collectors.reddit_collector import collect_reddit
from src.synthesizer.gemini_client import (
    synthesize_weekday,
    synthesize_weekend,
    generate_fallback_digest,
)
from src.generator.build_html import (
    generate_daily_html,
    generate_weekly_html,
    write_fallback_page,
    _write_error_page,
    cleanup_old_archives,
)
from src.config import SETTINGS


def _get_today_in_ist() -> datetime:
    """
    Return today's datetime in IST (Asia/Kolkata) timezone.

    Returns:
        Timezone-aware datetime in IST
    """
    try:
        from dateutil import tz
        ist = tz.gettz("Asia/Kolkata")
        return datetime.now(tz=ist)
    except ImportError:
        # Fallback: UTC+5:30 manually
        from datetime import timezone, timedelta
        ist = timezone(timedelta(hours=5, minutes=30))
        return datetime.now(tz=ist)


def _load_sample_data() -> list[Article]:
    """
    Load sample articles from the test fixture for dry-run mode.

    Returns:
        List of Article objects from sample_data.json
    """
    sample_path = Path(__file__).parent.parent / "tests" / "sample_data.json"
    if not sample_path.exists():
        logger.warning("Dry run: sample_data.json not found — using empty list")
        return []

    with open(sample_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    articles = []
    for item in raw:
        articles.append(Article(
            title=item.get("title", ""),
            url=item.get("url", ""),
            source_name=item.get("source_name", ""),
            source_type=item.get("source_type", ""),
            topic=item.get("topic", "ai_policy"),
            summary=item.get("summary", ""),
            published_at=item.get("published_at"),
            score=item.get("score"),
            comment_count=item.get("comment_count"),
        ))

    logger.info(f"Dry run: loaded {len(articles)} sample articles from {sample_path.name}")
    return articles


def _get_dry_run_digest(today: datetime, is_weekend: bool) -> dict:
    """
    Return a hardcoded sample digest JSON for dry-run mode.

    This lets you test the HTML generator without making any Gemini API calls.

    Args:
        today: Today's date
        is_weekend: Whether to return a weekend-format digest

    Returns:
        Sample digest dict
    """
    date_str = today.strftime("%B %d, %Y")
    day_str = today.strftime("%A")

    if is_weekend:
        return {
            "date": date_str,
            "day_of_week": "Saturday",
            "edition": "weekly_roundup",
            "week_summary": "This is a dry-run sample digest. The week was dominated by AI policy discussions, major tool launches, and strong earnings in the Indian startup ecosystem.",
            "top_stories_of_the_week": [
                {
                    "rank": 1,
                    "headline": "Sample: Major AI Regulation Passed in EU",
                    "summary": "The EU passed sweeping AI regulation this week. It requires transparency for all generative AI systems. This sets a global precedent for AI governance.",
                    "section": "ai_policy",
                    "source_url": "https://example.com/story1",
                },
                {
                    "rank": 2,
                    "headline": "Sample: Claude 4 Launches with Agentic Features",
                    "summary": "Anthropic shipped Claude 4 with long-context agent capabilities. PMs are already exploring it for product spec generation. Watch for workflow integrations.",
                    "section": "ai_tools",
                    "source_url": "https://example.com/story2",
                },
            ],
            "sections": {
                "ai_policy": {
                    "section_title": "AI Policy & Responsible Tech",
                    "week_in_review": "This is sample content. AI policy was the dominant story this week with multiple regulatory frameworks advancing globally.",
                    "key_stories": [
                        {
                            "title": "Sample Story: EU AI Act Implementation Begins",
                            "summary": "The EU AI Act moved into implementation phase. Firms now have 6 months to comply with transparency rules.",
                            "source_url": "https://example.com/ai-act",
                            "source_name": "Sample Source",
                        }
                    ],
                    "deep_read_recommendation": {
                        "title": "Understanding the EU AI Act: A PM's Guide",
                        "url": "https://example.com/deep-read",
                        "why": "Clear breakdown of what the Act means for product teams building AI features.",
                    },
                },
                "product_management": {"section_title": "Product Management in the AI Era", "week_in_review": "Sample PM content.", "key_stories": [], "deep_read_recommendation": {"title": "", "url": "", "why": ""}},
                "ai_tools": {"section_title": "AI Tools & Launches", "week_in_review": "Sample AI tools content.", "key_stories": [], "deep_read_recommendation": {"title": "", "url": "", "why": ""}},
                "india": {"section_title": "India — Broad Landscape", "week_in_review": "Sample India content.", "key_stories": [], "deep_read_recommendation": {"title": "", "url": "", "why": ""}},
                "content_creators": {"section_title": "Content Creator Trends", "week_in_review": "Sample creator content.", "key_stories": [], "deep_read_recommendation": {"title": "", "url": "", "why": ""}},
            },
            "pattern_of_the_week": "This is a sample pattern. The convergence of AI regulation and tool launches suggests a pivotal moment for the industry.",
        }

    return {
        "date": date_str,
        "day_of_week": day_str,
        "edition": "weekday",
        "top_3": [
            {
                "headline": "Sample: This is a Dry-Run Digest",
                "summary": "This digest was generated in dry-run mode (DRY_RUN=true). No Gemini API calls were made. Real content will appear on live runs.",
                "section": "ai_policy",
                "source_url": "https://example.com",
                "importance": "high",
            },
            {
                "headline": "Sample: Test Your HTML Template",
                "summary": "Open docs/index.html in your browser to verify the layout looks correct. Toggle dark mode with the button in the top-right.",
                "section": "ai_tools",
                "source_url": "https://example.com",
                "importance": "high",
            },
            {
                "headline": "Sample: Configure Your API Keys",
                "summary": "Add GEMINI_API_KEY to your GitHub Secrets to enable real synthesis. Optionally add REDDIT_CLIENT_ID for Reddit data.",
                "section": "product_management",
                "source_url": "https://aistudio.google.com/apikey",
                "importance": "high",
            },
        ],
        "sections": {
            "ai_policy": {
                "section_title": "AI Policy & Responsible Tech",
                "stories": [
                    {
                        "title": "Sample Story — AI Policy",
                        "summary": "This is a sample story. In a real digest, this would contain synthesized coverage of AI regulation, ethics developments, and responsible AI news from the past 24 hours.",
                        "source_url": "https://example.com/ai-policy",
                        "source_name": "Sample Source",
                    }
                ],
                "synthesis": "This is a sample synthesis paragraph. In a real digest, Gemini would connect the dots across all AI policy stories and identify the bigger pattern.",
            },
            "product_management": {
                "section_title": "Product Management in the AI Era",
                "stories": [],
                "synthesis": "No major developments today.",
            },
            "ai_tools": {
                "section_title": "AI Tools & Launches",
                "stories": [
                    {
                        "title": "Sample Story — AI Tool Launch",
                        "summary": "In a real digest, this section covers major launches and updates from Claude, ChatGPT, Cursor, Figma, and notable new tools. Minor patches are filtered out.",
                        "source_url": "https://example.com/ai-tools",
                        "source_name": "Sample Source",
                    }
                ],
                "synthesis": "Sample synthesis for AI tools section.",
            },
            "india": {
                "section_title": "India — Broad Landscape",
                "stories": [],
                "synthesis": "No major developments today.",
            },
            "content_creators": {
                "section_title": "Content Creator Trends",
                "stories": [
                    {
                        "title": "Sample: Carousel Format Outperforming Reels This Week",
                        "summary": "In a real digest, this section would contain specific, actionable creator trends. For example: carousel posts with the 'before/after' format are seeing 3x the saves compared to standard Reels this week.",
                        "source_url": "https://example.com/creator-trends",
                        "source_name": "Sample Source",
                    }
                ],
                "synthesis": "Sample synthesis for creator trends section.",
            },
        },
    }


def main() -> None:
    """
    Run the full PDD Agent pipeline.

    Determines edition type, collects articles, synthesizes with Gemini,
    generates HTML, and manages the archive.
    """
    logger.info("=" * 60)
    logger.info("PDD Agent — starting pipeline")
    logger.info("=" * 60)

    # ── 1. Check dry-run mode ──────────────────────────────────────────────────
    dry_run = os.environ.get("DRY_RUN", "").lower() in ("true", "1", "yes")
    if dry_run:
        logger.info("DRY RUN MODE — skipping real API calls, using sample data")

    # ── 2. Determine edition type ──────────────────────────────────────────────
    today = _get_today_in_ist()
    day_of_week = today.strftime("%A")
    logger.info(f"Today is {day_of_week}, {today.strftime('%Y-%m-%d')} (IST)")

    if day_of_week == "Sunday" and not dry_run:
        logger.info("Sunday — no digest generated. Exiting.")
        return

    is_weekend = day_of_week == "Saturday"
    logger.info(f"Edition: {'Weekly Roundup' if is_weekend else 'Weekday Daily'}")

    # ── 3. Collect articles ────────────────────────────────────────────────────
    if dry_run:
        all_articles = _load_sample_data()
    else:
        logger.info("Collecting articles from all sources...")
        all_articles = []
        all_articles += collect_safely(collect_google_news, "Google News")
        all_articles += collect_safely(collect_reddit, "Reddit")
        all_articles += collect_safely(collect_rss_feeds, "RSS Feeds")
        all_articles += collect_safely(collect_hackernews, "Hacker News")

    logger.info(f"Total articles before dedup: {len(all_articles)}")

    # ── 4. Handle zero articles ────────────────────────────────────────────────
    if len(all_articles) == 0:
        logger.error("No articles collected from any source. Generating error page.")
        _write_error_page(
            "No data sources were reachable today. All 4 collectors (Google News, Reddit, RSS, HackerNews) returned 0 articles.",
            today,
        )
        return

    # ── 5. Deduplicate ─────────────────────────────────────────────────────────
    all_articles = deduplicate_by_url(all_articles)
    all_articles = deduplicate_by_title_similarity(all_articles)
    logger.info(f"Total articles after dedup: {len(all_articles)}")

    # ── 6. Trim to top N per section (token budget management) ────────────────
    max_per = SETTINGS["max_articles_to_gemini"]
    trimmed_articles = trim_articles_per_section(all_articles, max_per_section=max_per)
    logger.info(f"Articles trimmed to {len(trimmed_articles)} (max {max_per}/section for Gemini)")

    # ── 7. Synthesize with Gemini ──────────────────────────────────────────────
    if dry_run:
        digest_json = _get_dry_run_digest(today, is_weekend)
        logger.info("Dry run: using hardcoded sample digest")
    elif is_weekend:
        digest_json = synthesize_weekend(trimmed_articles, today)
    else:
        digest_json = synthesize_weekday(trimmed_articles, today)

    # ── 8. Handle synthesis failure ────────────────────────────────────────────
    if digest_json is None:
        logger.error("Gemini synthesis returned None after all retries. Generating fallback page.")
        write_fallback_page(all_articles, today)
        return

    # ── 9. Generate HTML ───────────────────────────────────────────────────────
    logger.info("Generating HTML digest...")
    if is_weekend:
        generate_weekly_html(digest_json, all_articles, today)
    else:
        generate_daily_html(digest_json, all_articles, today)

    # ── 10. Archive management ─────────────────────────────────────────────────
    max_archive_days = SETTINGS.get("archive_days", 30)
    cleanup_old_archives(max_days=max_archive_days)

    logger.info("=" * 60)
    logger.info(f"PDD Agent — pipeline complete for {today.strftime('%Y-%m-%d')}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
