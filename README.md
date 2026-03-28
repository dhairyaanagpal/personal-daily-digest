# Personal Daily Digest (Use this to understand about the product)

An automated morning intelligence briefing that runs every day at **8:00 AM IST** — no subscriptions, no paywalls, no noise.

> Open one bookmarked URL every morning and get a 10-15 minute briefing on AI policy, product management, major tool launches, India news, and content creator trends.

**Cost: $0/month.** Zero paid APIs. Zero cloud servers.

---

## What it does

Every morning, the PDD Agent:
1. Crawls Google News RSS, Reddit, tech blogs, and Hacker News for your 5 configured topics
2. Deduplicates and filters to the highest-signal stories
3. Sends them to Google Gemini 2.0 Flash (free tier) for AI synthesis
4. Generates a beautiful static HTML dashboard
5. Deploys it to GitHub Pages — your one bookmarked URL is always fresh

**Saturday edition** is a weekly roundup instead of the daily — reflective, not reactive.
**Sundays** the agent rests.

---

## The 5 topic sections

| Section | What it covers |
|---------|----------------|
| 🔬 AI Policy & Responsible Tech | Regulation, ethics, epistemic security, governance |
| 📋 Product Management in the AI Era | PM workflows, frameworks, thought leadership |
| ⚡ AI Tools & Launches | Major updates to Claude, ChatGPT, Cursor, Figma, new tools |
| 🇮🇳 India — Broad Landscape | Politics, economy, startups, tech ecosystem |
| 📱 Content Creator Trends | Instagram, LinkedIn, Twitter/X formats that are working NOW |

---

## Architecture

```
GitHub Actions (cron: 2:30 UTC = 8:00 AM IST)
        │
        ▼
DATA COLLECTORS (4 Python scripts)
  ├── Google News RSS (no API key)
  ├── Reddit API (free tier, optional)
  ├── RSS feeds from blogs/newsletters (no API key)
  └── Hacker News API (no API key)
        │
        ▼ raw articles
SYNTHESIZER
  └── Google Gemini 2.0 Flash (free tier, 1500 req/day)
        │
        ▼ structured digest JSON
HTML GENERATOR
  └── Jinja2 templates + Tailwind CSS
        │
        ▼
GITHUB PAGES → docs/index.html (your morning URL)
```

---

## Setup

### 1. Fork or clone this repository

```bash
git clone https://github.com/yourusername/pdd-agent.git
cd pdd-agent
```

### 2. Install dependencies (for local testing)

```bash
pip install -r requirements.txt
```

### 3. Get your API keys

**Gemini API key (required):**
- Go to https://aistudio.google.com/apikey
- Sign in with Google → click "Create API key"
- It's free (1,500 requests/day on the free tier)

**Reddit credentials (optional — adds Reddit data, but not required):**
- Go to https://www.reddit.com/prefs/apps
- Click "create another app" → type: **script**
- Note the client ID (under the app name) and client secret

### 4. Add secrets to GitHub

In your repository: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Required | Value |
|-------------|----------|-------|
| `GEMINI_API_KEY` | ✅ Yes | Your Gemini API key |
| `REDDIT_CLIENT_ID` | Optional | Reddit app client ID |
| `REDDIT_CLIENT_SECRET` | Optional | Reddit app secret |

### 5. Enable GitHub Pages

- Go to **Settings → Pages**
- Source: **"Deploy from a branch"**
- Branch: `main` | Folder: `/docs`
- Click Save

Your digest will be available at: `https://yourusername.github.io/pdd-agent`

### 6. Test it

**Local dry run** (no API calls, uses sample data):
```bash
DRY_RUN=true python src/main.py
open docs/index.html  # view in browser
```

**Manual GitHub Actions trigger:**
- Go to **Actions → Daily PDD Digest → Run workflow**
- Set "Dry run" to `true` for a test without Gemini

---

## Customizing your topics

Everything lives in `src/config.py`:

- **`GOOGLE_NEWS_QUERIES`** — search queries for each topic section
- **`REDDIT_SUBREDDITS`** — subreddits to monitor per topic
- **`RSS_FEEDS`** — direct RSS feed URLs for blogs and newsletters
- **`HACKERNEWS_CONFIG`** — keyword filters for HN stories
- **`SETTINGS`** — timezone, archive days, articles per section, etc.

Edit these and push — the next run picks up your changes automatically.

---

## Testing individual components

```bash
# Test collectors standalone
python src/collectors/google_news.py
python src/collectors/hackernews.py
python src/collectors/rss_feeds.py
python src/collectors/reddit_collector.py  # requires Reddit env vars

# Run unit tests
python -m pytest tests/ -v

# Full pipeline dry run
DRY_RUN=true python src/main.py
```

---

## Tech stack

| Component | Tech |
|-----------|------|
| Language | Python 3.11 |
| Data collection | feedparser, requests, PRAW |
| AI synthesis | Google Gemini 2.0 Flash (google-generativeai) |
| HTML generation | Jinja2 + Tailwind CSS via CDN |
| Scheduling | GitHub Actions cron |
| Hosting | GitHub Pages |
| **Total cost** | **$0/month** |

---

## Resilience features

The agent is designed to never silently fail:

- **Every collector is isolated** — one broken source never crashes the pipeline
- **If ALL collectors fail** → error page explaining what went wrong
- **If Gemini is down** → fallback page with raw headlines, still useful
- **If HTML generation fails** → minimal error page always written
- **Every run** → `docs/index.html` is always updated with *something*

---

## Future plans

Things deliberately not built in v1 to keep it simple:

- Email delivery via SendGrid free tier
- Slack/Discord webhook for breaking news
- User preferences panel (adjust topics, digest length)
- RSS feed output for others to subscribe
- Multi-user support

---

## License

MIT — use it, fork it, build on it.
