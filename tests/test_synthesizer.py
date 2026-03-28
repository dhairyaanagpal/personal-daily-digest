"""
test_synthesizer.py — Tests for the Gemini synthesizer.

Tests JSON extraction, fallback digest generation, and prompt formatting.
Run with: python -m pytest tests/test_synthesizer.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import pytest
from datetime import datetime, timezone
from src.collectors.base import Article
from src.synthesizer.gemini_client import (
    _extract_json_from_response,
    _articles_to_json_string,
    generate_fallback_digest,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

TODAY = datetime(2025, 3, 27, 8, 0, tzinfo=timezone.utc)

SAMPLE_ARTICLES = [
    Article(
        title="EU AI Act Implementation Begins",
        url="https://example.com/eu-ai-act",
        source_name="MIT Tech Review",
        source_type="rss",
        topic="ai_policy",
        summary="The EU AI Act moved into implementation phase.",
        published_at="2025-03-27T06:00:00+00:00",
        score=None,
    ),
    Article(
        title="Claude 4 Launches with Agent Features",
        url="https://example.com/claude-4",
        source_name="Anthropic Blog",
        source_type="rss",
        topic="ai_tools",
        summary="Anthropic shipped Claude 4 with long-context agents.",
        published_at="2025-03-27T05:00:00+00:00",
        score=500,
    ),
]


# ─── JSON extraction tests ─────────────────────────────────────────────────────

class TestExtractJsonFromResponse:
    def test_parses_clean_json(self):
        payload = json.dumps({"date": "March 27", "edition": "weekday"})
        result = _extract_json_from_response(payload)
        assert result is not None
        assert result["edition"] == "weekday"

    def test_strips_markdown_fences(self):
        payload = "```json\n{\"date\": \"March 27\"}\n```"
        result = _extract_json_from_response(payload)
        assert result is not None
        assert result["date"] == "March 27"

    def test_extracts_json_from_surrounding_text(self):
        payload = "Here is the result:\n{\"date\": \"March 27\"}\nEnd of response."
        result = _extract_json_from_response(payload)
        assert result is not None

    def test_returns_none_for_invalid_json(self):
        result = _extract_json_from_response("This is not JSON at all.")
        assert result is None

    def test_returns_none_for_empty_string(self):
        result = _extract_json_from_response("")
        assert result is None

    def test_returns_none_for_none(self):
        result = _extract_json_from_response(None)
        assert result is None


# ─── Articles to JSON string tests ────────────────────────────────────────────

class TestArticlesToJsonString:
    def test_returns_valid_json(self):
        result = _articles_to_json_string(SAMPLE_ARTICLES)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_includes_required_fields(self):
        result = _articles_to_json_string(SAMPLE_ARTICLES)
        parsed = json.loads(result)
        assert "title" in parsed[0]
        assert "url" in parsed[0]
        assert "topic" in parsed[0]

    def test_truncates_long_summaries(self):
        long_article = Article(
            title="Test", url="https://example.com", source_name="Test",
            source_type="rss", topic="ai_policy",
            summary="x" * 1000,  # 1000 chars
        )
        result = _articles_to_json_string([long_article])
        parsed = json.loads(result)
        assert len(parsed[0]["summary"]) <= 300

    def test_handles_empty_list(self):
        result = _articles_to_json_string([])
        assert result == "[]"


# ─── Fallback digest tests ─────────────────────────────────────────────────────

class TestGenerateFallbackDigest:
    def test_returns_valid_structure(self):
        digest = generate_fallback_digest(SAMPLE_ARTICLES, TODAY)
        assert "date" in digest
        assert "sections" in digest
        assert "top_3" in digest

    def test_sections_contain_stories(self):
        digest = generate_fallback_digest(SAMPLE_ARTICLES, TODAY)
        # ai_tools section should have the Claude 4 story
        ai_tools = digest["sections"].get("ai_tools", {})
        assert len(ai_tools.get("stories", [])) >= 1

    def test_top_3_uses_highest_scored_articles(self):
        digest = generate_fallback_digest(SAMPLE_ARTICLES, TODAY)
        top_3 = digest["top_3"]
        assert len(top_3) >= 1
        # Claude 4 (score=500) should appear in top 3
        top_urls = [s["source_url"] for s in top_3]
        assert "https://example.com/claude-4" in top_urls

    def test_fallback_flag_is_set(self):
        digest = generate_fallback_digest(SAMPLE_ARTICLES, TODAY)
        assert digest.get("is_fallback") is True

    def test_handles_empty_articles(self):
        digest = generate_fallback_digest([], TODAY)
        assert digest is not None
        assert digest["top_3"] == []
