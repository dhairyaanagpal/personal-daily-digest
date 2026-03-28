"""
build_html.py — Jinja2-based HTML generator for PDD digest pages.

Takes a structured digest dict (from Gemini) and renders it to static HTML.
Handles daily, weekly, fallback, and error page generation.
Manages the archive directory and cleanup of old digests.
"""

import logging
import os
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from src.collectors.base import Article
from src.config import SETTINGS, SECTION_META

logger = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────
# Resolve relative to this file's location
_THIS_DIR = Path(__file__).parent
TEMPLATES_DIR = _THIS_DIR / "templates"
DOCS_DIR = Path(__file__).parent.parent.parent / "docs"
ARCHIVE_DIR = DOCS_DIR / "archive"

# ─── Section display metadata ─────────────────
SECTION_COLORS: dict[str, str] = {
    "ai_policy": "purple",
    "product_management": "teal",
    "ai_tools": "orange",
    "india": "green",
    "content_creators": "pink",
}

SECTION_ICONS: dict[str, str] = {
    "ai_policy": "🔬",
    "product_management": "📋",
    "ai_tools": "⚡",
    "india": "🇮🇳",
    "content_creators": "📱",
}

SECTION_TITLES: dict[str, str] = {
    "ai_policy": "AI Policy & Responsible Tech",
    "product_management": "Product Management in the AI Era",
    "ai_tools": "AI Tools & Launches",
    "india": "India — Broad Landscape",
    "content_creators": "Content Creator Trends",
}


def _get_jinja_env() -> Environment:
    """
    Create and return a Jinja2 environment pointing to our templates directory.

    Returns:
        Configured Jinja2 Environment
    """
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,  # escape HTML in all variables for safety
    )


def _get_archive_links(today: datetime, count: int = 7) -> list[dict]:
    """
    Build a list of archive links for the last N digests.

    Looks for actual files in the archive directory.

    Args:
        today: Today's date
        count: Number of past digests to link to

    Returns:
        List of dicts with 'label' and 'path' keys
    """
    links = []
    for i in range(1, count + 1):
        past_date = today - timedelta(days=i)
        date_str = past_date.strftime("%Y-%m-%d")
        archive_path = ARCHIVE_DIR / f"{date_str}.html"

        if archive_path.exists():
            links.append({
                "label": past_date.strftime("%b %d"),
                "path": f"archive/{date_str}.html",
            })

    return links


def _get_generated_time() -> str:
    """
    Return the current IST time formatted for display in the footer.

    Returns:
        Formatted time string, e.g. "08:05 AM"
    """
    try:
        from dateutil import tz
        ist = tz.gettz("Asia/Kolkata")
        now = datetime.now(tz=ist)
        return now.strftime("%I:%M %p")
    except Exception:
        return datetime.utcnow().strftime("%H:%M UTC")


def _compute_css_path(is_archive: bool = False) -> str:
    """
    Return the relative path to style.css from the output HTML location.

    Args:
        is_archive: True if the HTML file is inside docs/archive/

    Returns:
        Relative CSS path string
    """
    return "../style.css" if is_archive else "style.css"


def generate_daily_html(
    digest: dict,
    articles: list[Article],
    today: datetime,
) -> None:
    """
    Render the weekday digest template and write to docs/index.html and docs/archive/.

    Args:
        digest: Structured JSON dict from Gemini (weekday format)
        articles: All collected articles (used for the sources drawer)
        today: Today's date (used for archive naming)
    """
    env = _get_jinja_env()

    try:
        template = env.get_template("daily.html")
    except TemplateNotFound:
        logger.error("build_html: daily.html template not found")
        _write_error_page("Template file daily.html is missing.", today)
        return

    context = {
        "digest": digest,
        "all_articles": articles,
        "section_colors": SECTION_COLORS,
        "section_icons": SECTION_ICONS,
        "section_titles": SECTION_TITLES,
        "archive_links": _get_archive_links(today),
        "generated_time": _get_generated_time(),
        "css_path": _compute_css_path(is_archive=False),
    }

    try:
        html = template.render(**context)
        _write_html(html, today)
        logger.info(f"build_html: daily digest written to docs/index.html")
    except Exception as e:
        logger.error(f"build_html: template rendering failed: {e}", exc_info=True)
        _write_error_page(str(e), today)


def generate_weekly_html(
    digest: dict,
    articles: list[Article],
    today: datetime,
) -> None:
    """
    Render the weekly roundup template and write to docs/index.html and docs/archive/.

    Args:
        digest: Structured JSON dict from Gemini (weekly format)
        articles: All collected articles (used for the sources drawer)
        today: Today's date
    """
    env = _get_jinja_env()

    try:
        template = env.get_template("weekly.html")
    except TemplateNotFound:
        logger.error("build_html: weekly.html template not found")
        _write_error_page("Template file weekly.html is missing.", today)
        return

    context = {
        "digest": digest,
        "all_articles": articles,
        "section_colors": SECTION_COLORS,
        "section_icons": SECTION_ICONS,
        "section_titles": SECTION_TITLES,
        "archive_links": _get_archive_links(today),
        "generated_time": _get_generated_time(),
        "css_path": _compute_css_path(is_archive=False),
    }

    try:
        html = template.render(**context)
        _write_html(html, today)
        logger.info("build_html: weekly roundup written to docs/index.html")
    except Exception as e:
        logger.error(f"build_html: weekly template rendering failed: {e}", exc_info=True)
        _write_error_page(str(e), today)


def _write_html(html: str, today: datetime) -> None:
    """
    Write rendered HTML to docs/index.html and save a dated archive copy.

    Args:
        html: Rendered HTML string
        today: Today's date (used for archive filename)
    """
    # Ensure docs and archive dirs exist
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # Write latest digest
    index_path = DOCS_DIR / "index.html"
    index_path.write_text(html, encoding="utf-8")

    # Save archive copy
    date_str = today.strftime("%Y-%m-%d")
    archive_path = ARCHIVE_DIR / f"{date_str}.html"
    archive_path.write_text(html, encoding="utf-8")
    logger.info(f"build_html: archive saved to docs/archive/{date_str}.html")


def _write_error_page(error_message: str, today: datetime) -> None:
    """
    Write a minimal error page to docs/index.html so the user always sees something.

    Args:
        error_message: Description of what went wrong
        today: Today's date for display
    """
    date_str = today.strftime("%B %d, %Y")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PDD — Error</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-200 min-h-screen flex items-center justify-center p-8 font-sans">
  <div class="max-w-lg w-full text-center">
    <p class="text-6xl mb-6">⚠️</p>
    <h1 class="text-3xl font-bold mb-3">Generation Failed</h1>
    <p class="text-slate-400 mb-6">{date_str}</p>
    <div class="bg-slate-900 border border-slate-700 rounded-xl p-4 text-left mb-6">
      <p class="text-sm font-mono text-red-400">{error_message}</p>
    </div>
    <p class="text-slate-500 text-sm">Check the GitHub Actions log for details. The agent will retry at the next scheduled run.</p>
  </div>
</body>
</html>"""

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    logger.info("build_html: error page written to docs/index.html")


def write_fallback_page(articles: list[Article], today: datetime) -> None:
    """
    Write a raw headlines fallback page when Gemini is unavailable.

    Groups articles by topic and displays them as a simple list.
    Still useful — the user gets their morning headlines even without AI.

    Args:
        articles: All collected articles
        today: Today's date
    """
    from collections import defaultdict
    by_topic: dict[str, list[Article]] = defaultdict(list)
    for a in articles:
        by_topic[a.topic].append(a)

    date_str = today.strftime("%B %d, %Y")
    day_str = today.strftime("%A")

    sections_html = ""
    for topic, meta in SECTION_META.items():
        topic_articles = by_topic.get(topic, [])
        if not topic_articles:
            continue

        icon = SECTION_ICONS.get(topic, "📌")
        title = meta["title"]
        items_html = "\n".join(
            f'<li class="py-2 border-b border-slate-800 last:border-0">'
            f'<a href="{a.url}" target="_blank" class="text-slate-300 hover:text-amber-400 transition-colors">{a.title}</a>'
            f'<span class="ml-2 text-xs text-slate-500">— {a.source_name}</span>'
            f'</li>'
            for a in topic_articles[:10]
        )
        sections_html += f"""
        <section class="mb-8">
          <h2 class="text-lg font-bold text-white mb-3 flex items-center gap-2">
            <span>{icon}</span>{title}
          </h2>
          <ul class="bg-slate-900 border border-slate-700 rounded-xl p-4 text-sm">{items_html}</ul>
        </section>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Morning Briefing — {date_str}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
</head>
<body class="bg-slate-950 text-slate-200 min-h-screen font-sans">
  <div class="max-w-3xl mx-auto px-4 py-10">
    <div class="mb-6 p-4 bg-amber-900/30 border border-amber-700 rounded-xl text-amber-300 text-sm">
      ⚠️ <strong>AI synthesis unavailable</strong> — showing raw headlines. Full synthesis will resume at next run.
    </div>
    <h1 class="text-4xl font-bold text-white mb-1">Morning Briefing</h1>
    <p class="text-slate-400 mb-8">{day_str}, {date_str}</p>
    {sections_html}
    <footer class="border-t border-slate-800 pt-6 mt-10 text-xs text-slate-500 text-center">
      Generated by PDD Agent (fallback mode)
    </footer>
  </div>
</body>
</html>"""

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")

    date_archive = ARCHIVE_DIR / f"{today.strftime('%Y-%m-%d')}.html"
    date_archive.write_text(html, encoding="utf-8")

    logger.info("build_html: fallback page written to docs/index.html")


def cleanup_old_archives(max_days: int = 30) -> None:
    """
    Delete archive HTML files older than max_days.

    Args:
        max_days: Number of days to retain in the archive
    """
    if not ARCHIVE_DIR.exists():
        return

    cutoff = datetime.now() - timedelta(days=max_days)
    removed = 0

    for html_file in ARCHIVE_DIR.glob("*.html"):
        # Archive files are named YYYY-MM-DD.html
        try:
            file_date = datetime.strptime(html_file.stem, "%Y-%m-%d")
            if file_date < cutoff:
                html_file.unlink()
                removed += 1
        except ValueError:
            pass  # skip files that don't match the date pattern

    if removed > 0:
        logger.info(f"build_html: cleaned up {removed} old archive files (>{max_days} days)")


# ─── Placeholder page for initial GitHub Pages setup ─────────────────────────
def write_placeholder_index() -> None:
    """
    Write a placeholder index.html so GitHub Pages has something to serve
    before the first real digest run.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Personal Daily Digest — Loading</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Playfair+Display:wght@700&display=swap" rel="stylesheet" />
</head>
<body class="bg-slate-950 text-slate-200 min-h-screen flex items-center justify-center font-sans">
  <div class="text-center max-w-md px-6">
    <p class="text-5xl mb-6">📰</p>
    <h1 class="font-serif text-4xl font-bold text-white mb-3">Personal Daily Digest</h1>
    <p class="text-slate-400 mb-6 leading-relaxed">
      Your morning intelligence briefing is being set up. The first digest will arrive at 8:00 AM IST.
    </p>
    <div class="inline-flex items-center gap-2 text-sm text-amber-500 bg-amber-500/10 border border-amber-500/20 rounded-full px-4 py-2">
      <span class="w-2 h-2 bg-amber-500 rounded-full animate-pulse"></span>
      Waiting for first digest run
    </div>
  </div>
</body>
</html>"""

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    placeholder = DOCS_DIR / "index.html"
    if not placeholder.exists():
        placeholder.write_text(html, encoding="utf-8")
        logger.info("build_html: placeholder index.html created")
