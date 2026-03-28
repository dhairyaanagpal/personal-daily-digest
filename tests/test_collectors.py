"""
test_collectors.py — Unit tests for data collectors.

Tests deduplication logic, Article dataclass, and collector error handling.
Run with: python -m pytest tests/test_collectors.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.collectors.base import (
    Article,
    deduplicate_by_url,
    deduplicate_by_title_similarity,
    trim_articles_per_section,
    collect_safely,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_article(
    title="Test Article",
    url="https://example.com/test",
    topic="ai_policy",
    score=None,
    published_at=None,
) -> Article:
    return Article(
        title=title,
        url=url,
        source_name="Test Source",
        source_type="rss",
        topic=topic,
        summary="Test summary.",
        published_at=published_at,
        score=score,
    )


# ─── Article dataclass tests ───────────────────────────────────────────────────

class TestArticle:
    def test_to_dict_returns_all_fields(self):
        a = make_article()
        d = a.to_dict()
        assert "title" in d
        assert "url" in d
        assert "source_name" in d
        assert "topic" in d
        assert d["title"] == "Test Article"

    def test_repr_truncates_long_title(self):
        a = make_article(title="A" * 100)
        rep = repr(a)
        assert len(rep) < 200  # repr should not explode in length


# ─── Deduplication tests ───────────────────────────────────────────────────────

class TestDeduplicateByUrl:
    def test_removes_exact_url_duplicates(self):
        articles = [
            make_article(url="https://example.com/story-1"),
            make_article(url="https://example.com/story-2"),
            make_article(url="https://example.com/story-1"),  # duplicate
        ]
        result = deduplicate_by_url(articles)
        assert len(result) == 2

    def test_strips_trailing_slash(self):
        articles = [
            make_article(url="https://example.com/story/"),
            make_article(url="https://example.com/story"),   # same without slash
        ]
        result = deduplicate_by_url(articles)
        assert len(result) == 1

    def test_preserves_order(self):
        articles = [
            make_article(title="First", url="https://example.com/1"),
            make_article(title="Second", url="https://example.com/2"),
        ]
        result = deduplicate_by_url(articles)
        assert result[0].title == "First"
        assert result[1].title == "Second"

    def test_empty_list(self):
        assert deduplicate_by_url([]) == []


class TestDeduplicateByTitleSimilarity:
    def test_removes_similar_titles_in_same_topic(self):
        articles = [
            make_article(title="EU passes major AI regulation law", url="https://a.com/1", topic="ai_policy"),
            make_article(title="EU passes sweeping AI regulation", url="https://b.com/2", topic="ai_policy"),
        ]
        result = deduplicate_by_title_similarity(articles)
        assert len(result) == 1

    def test_keeps_similar_titles_in_different_topics(self):
        # Same words but different topics = keep both
        articles = [
            make_article(title="AI regulation passes today", url="https://a.com/1", topic="ai_policy"),
            make_article(title="AI regulation passes today", url="https://b.com/2", topic="india"),
        ]
        result = deduplicate_by_title_similarity(articles)
        assert len(result) == 2

    def test_keeps_higher_scored_article(self):
        articles = [
            make_article(title="EU passes major AI regulation", url="https://a.com/1", score=10),
            make_article(title="EU passes sweeping AI regulation", url="https://b.com/2", score=500),
        ]
        result = deduplicate_by_title_similarity(articles)
        assert len(result) == 1
        assert result[0].score == 500


# ─── Trim articles tests ───────────────────────────────────────────────────────

class TestTrimArticlesPerSection:
    def test_keeps_max_per_section(self):
        articles = [make_article(url=f"https://example.com/{i}") for i in range(20)]
        result = trim_articles_per_section(articles, max_per_section=5)
        assert len(result) == 5

    def test_keeps_all_if_under_limit(self):
        articles = [make_article(url=f"https://example.com/{i}") for i in range(3)]
        result = trim_articles_per_section(articles, max_per_section=10)
        assert len(result) == 3

    def test_handles_multiple_topics(self):
        ai_articles = [make_article(url=f"https://a.com/{i}", topic="ai_policy") for i in range(8)]
        pm_articles = [make_article(url=f"https://p.com/{i}", topic="product_management") for i in range(8)]
        result = trim_articles_per_section(ai_articles + pm_articles, max_per_section=5)
        assert len(result) == 10  # 5 per topic

    def test_prefers_higher_scored_articles(self):
        articles = [
            make_article(url="https://example.com/low", score=1),
            make_article(url="https://example.com/high", score=999),
            make_article(url="https://example.com/mid", score=50),
        ]
        result = trim_articles_per_section(articles, max_per_section=1)
        assert result[0].score == 999


# ─── collect_safely tests ──────────────────────────────────────────────────────

class TestCollectSafely:
    def test_returns_articles_on_success(self):
        def good_collector():
            return [make_article()]

        result = collect_safely(good_collector, "TestCollector")
        assert len(result) == 1

    def test_returns_empty_on_exception(self):
        def broken_collector():
            raise RuntimeError("Network error")

        result = collect_safely(broken_collector, "BrokenCollector")
        assert result == []

    def test_returns_empty_on_any_exception_type(self):
        def another_broken():
            raise ValueError("Unexpected value")

        result = collect_safely(another_broken, "AnotherBroken")
        assert result == []
