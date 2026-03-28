"""
config.py — Single source of truth for all PDD Agent configuration.

All queries, feed URLs, subreddits, and settings live here.
Edit this file to customize your digest topics, sources, and behavior.
"""

# ─────────────────────────────────────────────
# GOOGLE NEWS RSS QUERIES
# URL format: https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en
# ─────────────────────────────────────────────

GOOGLE_NEWS_QUERIES: dict[str, list[str]] = {
    "ai_policy": [
        "AI policy regulation 2025",
        "responsible AI ethics",
        "AI governance",
        "epistemic security misinformation AI",
        "AI regulation India",
    ],
    "product_management": [
        "product management AI tools",
        "product manager role evolution AI",
        "PM strategy artificial intelligence",
        "product management 2025 trends",
    ],
    "ai_tools": [
        "Claude Anthropic update launch",
        "OpenAI ChatGPT new feature",
        "Cursor AI editor update",
        "Figma AI update",
        "new AI tool launch 2025",
    ],
    "india": [
        "India politics today",
        "India economy market today",
        "India startup funding 2025",
        "India technology policy",
        "India AI policy",
    ],
    "content_creators": [
        "Instagram Reels trends 2025",
        "LinkedIn content strategy trending",
        "social media content creator trends",
        "Twitter X viral format trending",
        "content creator algorithm 2025",
    ],
}

# ─────────────────────────────────────────────
# REDDIT SUBREDDITS
# Using PRAW to get top posts from the last 24 hours
# ─────────────────────────────────────────────

REDDIT_SUBREDDITS: dict[str, list[str]] = {
    "ai_policy": ["artificial", "MachineLearning"],
    "product_management": ["ProductManagement"],
    "ai_tools": ["ChatGPT", "ClaudeAI", "cursor", "LocalLLaMA"],
    "india": ["india", "IndianStartups", "indiainvestments"],
    "content_creators": ["Instagram", "socialmedia", "linkedin"],
}

# ─────────────────────────────────────────────
# RSS FEED URLs
# Direct blog/newsletter RSS feeds to parse with feedparser.
# If a URL is dead/broken, comment it out — don't let it block the pipeline.
# ─────────────────────────────────────────────

RSS_FEEDS: dict[str, list[str]] = {
    "ai_policy": [
        "https://www.anthropic.com/rss.xml",
        "https://openai.com/blog/rss.xml",
        "https://www.technologyreview.com/feed/",          # MIT Tech Review
        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    ],
    "product_management": [
        "https://www.lennysnewsletter.com/feed",           # Lenny's Newsletter (public posts only)
        "https://review.firstround.com/feed",              # First Round Review
        "https://www.producttalk.org/feed/",               # Product Talk by Teresa Torres
    ],
    "ai_tools": [
        "https://www.anthropic.com/rss.xml",
        "https://openai.com/blog/rss.xml",
        "https://www.producthunt.com/feed",                # Product Hunt launches
        "https://news.ycombinator.com/rss",                # Hacker News (supplemental)
    ],
    "india": [
        "https://techcrunch.com/tag/india/feed/",
        "https://inc42.com/feed/",                         # Inc42 — India tech/startup news
        "https://entrackr.com/feed/",                      # Entrackr — India startup tracker
    ],
    "content_creators": [
        "https://www.socialmediaexaminer.com/feed/",       # Social Media Examiner
        "https://later.com/blog/feed/",                    # Later.com — social media tips
        "https://buffer.com/resources/feed/",              # Buffer blog
    ],
}

# ─────────────────────────────────────────────
# HACKER NEWS SETTINGS
# Uses the public Firebase API — no auth required
# ─────────────────────────────────────────────

HACKERNEWS_CONFIG: dict = {
    "top_stories_url": "https://hacker-news.firebaseio.com/v0/topstories.json",
    "item_url": "https://hacker-news.firebaseio.com/v0/item/{id}.json",
    "max_stories": 30,      # fetch top 30, then filter for relevance
    "min_score": 20,        # only include stories with score > 20
    "relevant_keywords": [
        "AI", "LLM", "GPT", "Claude", "Anthropic", "OpenAI", "Cursor",
        "Figma", "product management", "India", "startup",
        "Instagram", "LinkedIn", "content creator", "machine learning",
        "artificial intelligence", "language model", "agent",
    ],
}

# ─────────────────────────────────────────────
# GENERAL SETTINGS
# ─────────────────────────────────────────────

SETTINGS: dict = {
    "timezone": "Asia/Kolkata",
    "digest_time": "08:00",             # display time on the digest
    "max_articles_per_section": 15,     # raw articles to collect per section
    "max_articles_to_gemini": 10,       # articles per section to send to Gemini
    "max_stories_per_section_output": 4,  # stories in final digest per section
    "top_headlines_count": 3,
    "weekday_edition": True,            # Mon-Fri = full digest
    "weekend_edition": True,            # Saturday = weekly roundup
    "skip_sunday": True,                # no digest on Sunday
    "archive_days": 30,                 # keep last 30 digests in archive
    "rss_max_age_hours": 48,            # only include articles from last 48 hours
    "request_timeout": 15,             # seconds before giving up on an HTTP request
    "gemini_model": "gemini-2.5-flash",   # fallbacks tried in order by gemini_client.py
    "gemini_temperature": 0.3,
    "gemini_max_retries": 3,
    "gemini_retry_delay": 5,            # seconds to wait between retries
}

# ─────────────────────────────────────────────
# SECTION METADATA
# Used by the HTML generator for display names, colors, and icons
# ─────────────────────────────────────────────

SECTION_META: dict[str, dict] = {
    "ai_policy": {
        "title": "AI Policy & Responsible Tech",
        "icon": "🔬",
        "color_class": "purple",        # Tailwind color prefix
        "description": "Regulation, ethics, epistemic security, and responsible AI",
    },
    "product_management": {
        "title": "Product Management in the AI Era",
        "icon": "📋",
        "color_class": "teal",
        "description": "How PMs are evolving with AI tools, frameworks, and workflows",
    },
    "ai_tools": {
        "title": "AI Tools & Launches",
        "icon": "⚡",
        "color_class": "orange",
        "description": "Major updates to Claude, ChatGPT, Cursor, Figma, and new tools",
    },
    "india": {
        "title": "India — Broad Landscape",
        "icon": "🇮🇳",
        "color_class": "green",
        "description": "Politics, economy, tech ecosystem, and startup news",
    },
    "content_creators": {
        "title": "Content Creator Trends",
        "icon": "📱",
        "color_class": "pink",
        "description": "Trending formats on Instagram, LinkedIn, Twitter/X, and Reddit",
    },
}

# All valid topic keys — used for validation throughout the codebase
VALID_TOPICS: list[str] = list(SECTION_META.keys())
