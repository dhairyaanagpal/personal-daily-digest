# CLAUDE.md — Personal Daily Digest (PDD Agent)

This file is the complete reference for the PDD Agent project. If context expires, start here. Everything needed to understand, maintain, and extend this project is in this file.̌

---

## What this project is

The **Personal Daily Digest (PDD) Agent** is a fully automated morning intelligence briefing system. It runs every day at **8:00 AM IST** via GitHub Actions, crawls the internet for news across 5 curated topic areas, sends the raw content to **Google Gemini 2.5 Flash** for AI synthesis, generates a beautiful static HTML dashboard, and deploys it to **GitHub Pages**.

The user opens one bookmarked URL every morning and gets a 10–15 minute intelligence briefing covering exactly what they care about.

**Total cost: $0/month.** No paid APIs. No cloud servers. No subscriptions.

---

## Who the user is

- **Dhairya Nagpal** — a technical product manager based in **India (IST timezone)**
- Not a full-time developer — code must be clean, readable, and well-commented
- Wants to stay updated on AI policy, product management, India news, and content creator trends
- Will use this every single morning as their primary news source
- Building this in public — may write about it on Substack
- GitHub username: `dhairyaanagpal`
- GitHub repo: `https://github.com/dhairyaanagpal/personal-daily-digest`

---

## Architecture

```
GitHub Actions (cron: 2:30 UTC = 8:00 AM IST, Mon–Sat)
        │
        ▼
DATA COLLECTORS (4 Python scripts)
  ├── Google News RSS        — no API key, ~2000 articles/run
  ├── Reddit API (PRAW)      — optional, requires secrets
  ├── RSS feeds (feedparser) — blogs and newsletters
  └── Hacker News Firebase   — no API key
        │
        ▼ raw articles (Article dataclass)
DEDUPLICATION
  ├── By exact URL
  └── By title similarity (Jaccard ≥ 0.50, within same topic)
        │
        ▼ trimmed to 10 articles/section
SYNTHESIZER
  └── Google Gemini 2.5 Flash (free tier)
      Fallback order: gemini-2.5-flash → gemini-2.0-flash → gemini-2.0-flash-lite → gemini-flash-latest
        │
        ▼ structured JSON digest
HTML GENERATOR
  └── Jinja2 templates + Tailwind CSS (CDN, no build step)
        │
        ▼
GITHUB PAGES
  └── docs/index.html    — latest digest (overwritten each run)
  └── docs/archive/      — dated archive, kept for 30 days
```

---

## The 5 topic sections (in display order)

### Section 1: AI Policy & Responsible Tech (`ai_policy`) — 🔬 Purple
- AI regulation and policy (global + India-specific)
- Responsible AI and ethics developments
- Epistemic security, misinformation, deepfakes
- Major AI research breakthroughs that affect policy

### Section 2: Product Management in the AI Era (`product_management`) — 📋 Teal
- How PMs are adapting workflows to AI tools
- New PM frameworks, methodologies, and thinking
- Role evolution — what PMs do now vs before
- PM thought leadership and industry trends

### Section 3: AI Tools & Launches (`ai_tools`) — ⚡ Orange
ONLY major launches and big updates, NOT minor patches:
- Claude / Claude Code (Anthropic)
- ChatGPT / OpenAI (GPT models, API changes)
- Cursor (AI code editor)
- Figma AI features
- Any notable NEW AI tool (via Product Hunt / Hacker News)

### Section 4: India — Broad Landscape (`india`) — 🇮🇳 Green
- National politics and policy decisions
- Economy, markets, and financial news
- Tech and startup ecosystem (funding, launches, exits)
- India-specific tech/AI policy

### Section 5: Content Creator Trends (`content_creators`) — 📱 Pink
ACTIONABLE trends only, not vague commentary:
- Instagram: Reels/carousel/Stories formats that are performing
- LinkedIn: post formats getting engagement
- Twitter/X: viral formats and algorithm shifts
- Reddit: rising communities and trending discussion formats

---

## Complete file structure (as built)

```
pdd-agent/
├── .github/
│   └── workflows/
│       └── daily-digest.yml        # GitHub Actions cron (2:30 UTC = 8 AM IST, Mon–Sat)
├── src/
│   ├── __init__.py
│   ├── main.py                     # ENTRY POINT — orchestrates full pipeline
│   ├── config.py                   # ALL config: queries, URLs, subreddits, settings
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base.py                 # Article dataclass + dedup + trim utilities
│   │   ├── google_news.py          # Google News RSS collector
│   │   ├── reddit_collector.py     # Reddit API (PRAW) — optional
│   │   ├── rss_feeds.py            # Generic RSS feed collector
│   │   └── hackernews.py           # Hacker News Firebase API
│   ├── synthesizer/
│   │   ├── __init__.py
│   │   ├── gemini_client.py        # Gemini API wrapper — new google-genai SDK
│   │   └── prompts.py              # Weekday + weekend LLM prompts
│   └── generator/
│       ├── __init__.py
│       ├── build_html.py           # Jinja2 renderer + archive manager
│       └── templates/
│           ├── base.html           # Shared layout: nav, dark mode, footer
│           ├── daily.html          # Weekday template (Mon–Fri)
│           └── weekly.html         # Saturday roundup template
├── docs/                           # GitHub Pages serves from here
│   ├── index.html                  # Latest digest (auto-overwritten each run)
│   ├── archive/                    # Past digests: YYYY-MM-DD.html
│   └── style.css                   # Custom styles on top of Tailwind
├── tests/
│   ├── test_collectors.py          # 31 unit tests — all passing
│   ├── test_synthesizer.py
│   └── sample_data.json            # 15 sample articles for dry-run testing
├── .env                            # LOCAL ONLY — never commit. Contains GEMINI_API_KEY
├── .gitignore                      # .env is gitignored
├── requirements.txt
├── README.md
└── CLAUDE.md                       # This file
```

---

## Environment variables

| Variable | Required | Where to set |
|----------|----------|--------------|
| `GEMINI_API_KEY` | YES | `.env` for local, GitHub Secrets for Actions |
| `REDDIT_CLIENT_ID` | Optional | Same — adds Reddit data source |
| `REDDIT_CLIENT_SECRET` | Optional | Same |

The `.env` file is gitignored and must never be committed. For GitHub Actions, add secrets at: Settings → Secrets and variables → Actions → New repository secret.

---

## Key implementation decisions made during build

### SDK: google-genai (NOT google-generativeai)
The old `google-generativeai` package is deprecated. We use the new `google-genai>=1.0.0` SDK.

```python
from google import genai
from google.genai import types
client = genai.Client(api_key=api_key)
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        temperature=0.3,
        response_mime_type="application/json"
    )
)
```

### Model: gemini-2.5-flash (primary)
`gemini-2.0-flash` showed quota `limit: 0` on the free tier for this API key. `gemini-2.5-flash` works. The client automatically probes and falls back through the model list.

### python-dotenv for local runs
`main.py` calls `load_dotenv()` so `python3 src/main.py` works locally without manually exporting env vars. Note: `python-dotenv` must be in `requirements.txt` — it was accidentally removed at one point, add it back if missing.

### Python compatibility
GitHub Actions uses Python 3.11. Local machine is Python 3.9.6. Files using `X | Y` union syntax must include `from __future__ import annotations` at the top.

### Deduplication threshold
Title similarity uses Jaccard at **0.50** (not 0.70). Lower threshold needed because 2-letter tokens like "EU" and "AI" were being filtered, reducing overlap scores on clearly duplicate titles.

### RSS feeds — known broken ones (as of 2026-03-28)
These fail gracefully — the agent logs a warning and continues:
- `https://www.anthropic.com/rss.xml` — malformed XML
- `https://review.firstround.com/feed` — malformed XML
- `https://entrackr.com/feed/` — syntax error
- `https://later.com/blog/feed/` — malformed XML
- `https://buffer.com/resources/feed/` — malformed XML

Google News picks up this content regardless. These should be replaced with working alternatives when time permits.

---

## Google News queries (config.py)

```python
GOOGLE_NEWS_QUERIES = {
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
```

---

## Reddit subreddits (config.py)

```python
REDDIT_SUBREDDITS = {
    "ai_policy":          ["artificial", "MachineLearning"],
    "product_management": ["ProductManagement"],
    "ai_tools":           ["ChatGPT", "ClaudeAI", "cursor", "LocalLLaMA"],
    "india":              ["india", "IndianStartups", "indiainvestments"],
    "content_creators":   ["Instagram", "socialmedia", "linkedin"],
}
```

Reddit is optional — skipped gracefully if `REDDIT_CLIENT_ID` is not set.

---

## General settings (config.py)

```python
SETTINGS = {
    "timezone": "Asia/Kolkata",
    "digest_time": "08:00",
    "max_articles_per_section": 15,
    "max_articles_to_gemini": 10,
    "max_stories_per_section_output": 4,
    "top_headlines_count": 3,
    "weekday_edition": True,          # Mon–Fri
    "weekend_edition": True,          # Saturday = weekly roundup
    "skip_sunday": True,
    "archive_days": 30,
    "rss_max_age_hours": 48,
    "request_timeout": 15,
    "gemini_model": "gemini-2.5-flash",
    "gemini_temperature": 0.3,
    "gemini_max_retries": 3,
    "gemini_retry_delay": 5,
}
```

---

## How to run locally

```bash
# Full live run (.env is loaded automatically)
python3 src/main.py

# Dry run — no API calls, uses tests/sample_data.json
DRY_RUN=true python3 src/main.py

# Run all unit tests (31 tests, all passing)
python3 -m pytest tests/ -v

# Test individual collectors
python3 src/collectors/google_news.py
python3 src/collectors/hackernews.py
python3 src/collectors/rss_feeds.py
```

---

## GitHub Actions workflow

File: `.github/workflows/daily-digest.yml`
- **Schedule**: `30 2 * * 1-6` → 2:30 AM UTC = 8:00 AM IST, Monday–Saturday
- **Manual trigger**: workflow_dispatch with optional `dry_run` input
- **Steps**: checkout → install deps → `python src/main.py` → git commit + push `docs/`
- **GitHub Pages**: served from `docs/` folder on `main` branch

---

## HTML dashboard design

- **Framework**: Tailwind CSS via CDN (no build step needed)
- **Fonts**: Inter (body) + Playfair Display (headings) via Google Fonts
- **Dark mode**: toggle in top-right, preference saved in localStorage
- **Animations**: staggered fade-up on section card load
- **Layout**: max-w-4xl centered, fully mobile responsive

**Weekday template** (`daily.html`):
1. Sticky top bar + dark mode toggle
2. "Morning Briefing" header + date
3. Top 3 hero cards — amber numbered badges, visually prominent
4. 5 section cards: ai_policy → product_management → ai_tools → india → content_creators
5. Each section: story cards + "Pattern & Context" synthesis block at bottom
6. Collapsible sources drawer (all raw article links)
7. Archive nav (last 7 days of digests)
8. Footer with generated time

**Saturday template** (`weekly.html`):
1. "The Week in Review" header
2. Amber "This Week at a Glance" summary block
3. Ranked top stories of the week (1–7)
4. Per-section: week_in_review paragraph + key stories + deep read recommendation
5. "Pattern of the Week" inverted dark callout block

**Section colors**:
| Section key | Color | Pill class |
|-------------|-------|------------|
| `ai_policy` | Purple | `pill-purple` |
| `product_management` | Teal | `pill-teal` |
| `ai_tools` | Orange | `pill-orange` |
| `india` | Green | `pill-green` |
| `content_creators` | Pink | `pill-pink` |

---

## Resilience — the pipeline never silently fails

1. Every collector wrapped in `collect_safely()` — one broken source never crashes the run
2. All collectors fail → error page written to `docs/index.html`
3. Gemini fails after 3 retries → fallback page with raw headlines (still useful)
4. HTML generation fails → minimal error page always written
5. JSON from Gemini: direct parse → strip markdown fences → regex `{...}` extract → fallback
6. `docs/index.html` is **always** updated with something on every run

---

## Python dependencies (requirements.txt)

```
python-dotenv==1.0.1
feedparser==6.0.11
requests==2.31.0
praw==7.7.1
google-genai>=1.0.0
jinja2==3.1.4
python-dateutil==2.9.0
```

Note: `python-dotenv` is required for local `.env` loading. If it goes missing from `requirements.txt`, add it back.

---

## Current status (as of 2026-03-28)

- Full pipeline built and working end-to-end
- First successful live run: Saturday 2026-03-28 (weekly roundup edition)
- ~2,000 articles collected per run, deduplicated to ~1,900, trimmed to 50 for Gemini
- Gemini synthesis takes ~60 seconds with gemini-2.5-flash
- 31/31 unit tests passing
- **Pending**: GitHub push (need valid PAT — token must start with `ghp_`)
- **Pending**: Add `GEMINI_API_KEY` as GitHub repository secret
- **Pending**: Enable GitHub Pages (Settings → Pages → Branch: main → Folder: /docs)

---

## What still needs to be done

- [ ] Get valid GitHub PAT (ghp_...) and push repo to `dhairyaanagpal/personal-daily-digest`
- [ ] Add `GEMINI_API_KEY` as GitHub Actions secret
- [ ] Enable GitHub Pages
- [ ] Trigger first automated GitHub Actions run and verify it works
- [ ] Fix or replace the 5 broken RSS feed URLs in `src/config.py`

---

## Stretch goals (not in v1)

- Email delivery via free SendGrid tier
- Slack/Discord webhook for breaking news
- "Breaking news" alert if a story scores above a threshold
- User preferences panel (adjust topics, digest length)
- RSS feed output for others to subscribe
- Multi-user support

---

## Rules for future Claude sessions

1. **Never hardcode API keys** — `.env` locally, GitHub Secrets in Actions
2. **Never commit `.env`** — it is gitignored
3. **Use `google-genai`** not `google-generativeai` (deprecated)
4. **Primary model is `gemini-2.5-flash`** — `gemini-2.0-flash` has quota issues on this key
5. **Python 3.9 locally, 3.11 in Actions** — use `from __future__ import annotations` for `X | Y` unions
6. **`src/config.py` is the single source of truth** — all queries, feeds, subreddits, settings live there
7. **`src/synthesizer/prompts.py` is carefully crafted** — do not simplify or shorten the prompts
8. **The HTML must look premium** — this is what the user sees every single morning
9. **Always test with `DRY_RUN=true python3 src/main.py`** before a live run
10. **`docs/` must never be gitignored** — GitHub Pages depends on it being committed
11. **`python-dotenv` must stay in `requirements.txt`** — it was accidentally removed once already
