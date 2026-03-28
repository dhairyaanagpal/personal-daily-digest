"""
gemini_client.py — Google Gemini API wrapper for the PDD synthesizer.

Uses the new `google-genai` SDK (the old `google-generativeai` is deprecated).
Includes retry logic, JSON extraction, and fallback handling.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Optional

from src.collectors.base import Article
from src.config import SETTINGS, SECTION_META
from src.synthesizer.prompts import WEEKDAY_PROMPT, WEEKEND_PROMPT

logger = logging.getLogger(__name__)

TEMPERATURE = SETTINGS["gemini_temperature"]
MAX_RETRIES = SETTINGS["gemini_max_retries"]
RETRY_DELAY = SETTINGS["gemini_retry_delay"]

# Model preference order — first one that responds without a quota error wins.
# gemini-2.5-flash is the current recommended free-tier model.
MODEL_CANDIDATES = [
    SETTINGS["gemini_model"],     # gemini-2.5-flash (from config)
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
]


def _get_client():
    """
    Create and return a google-genai Client configured with the API key.

    Returns:
        google.genai.Client, or None if the key is missing / SDK unavailable
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable is not set")
        return None

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        logger.debug("Gemini: client initialized")
        return client
    except ImportError:
        logger.error("Gemini: google-genai not installed. Run: pip install google-genai")
        return None


def _call_model(client, model_name: str, prompt: str) -> Optional[str]:
    """
    Attempt a single generate_content call with a specific model.

    Args:
        client: google.genai.Client
        model_name: Model identifier string
        prompt: Full prompt text

    Returns:
        Response text, or None if the call failed
    """
    try:
        from google.genai import types
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=TEMPERATURE,
                response_mime_type="application/json",
            ),
        )
        return response.text
    except Exception as e:
        logger.warning(f"Gemini [{model_name}]: {e}")
        return None


def _find_working_model(client) -> Optional[str]:
    """
    Try each model candidate with a minimal probe request to find one that works.

    This handles quota exhaustion on gemini-2.0-flash by automatically
    falling back to gemini-1.5-flash etc.

    Returns:
        Model name string that responded successfully, or None
    """
    probe = '{"test": true}'
    for model in MODEL_CANDIDATES:
        try:
            from google.genai import types
            response = client.models.generate_content(
                model=model,
                contents=f"Reply with only this JSON: {probe}",
                config=types.GenerateContentConfig(temperature=0),
            )
            if response.text:
                logger.info(f"Gemini: using model '{model}'")
                return model
        except Exception as e:
            logger.warning(f"Gemini: model '{model}' unavailable — {e}")
            continue
    return None


def _extract_json_from_response(text: Optional[str]) -> Optional[dict]:
    """
    Parse JSON from Gemini's response text.

    Tries direct parse first, then strips markdown fences, then regex extracts
    the outermost { } block.

    Args:
        text: Raw text response from Gemini

    Returns:
        Parsed dict, or None if no valid JSON found
    """
    if not text:
        return None

    # Attempt 1: direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Attempt 2: strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Attempt 3: extract outermost { } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    logger.error("Gemini: could not extract valid JSON from response")
    logger.debug(f"Raw response (first 500 chars): {text[:500]}")
    return None


def _articles_to_json_string(articles: list[Article]) -> str:
    """
    Convert articles to a compact JSON string for inclusion in the prompt.

    Trims each article to the fields Gemini actually needs.
    """
    article_dicts = []
    for a in articles:
        article_dicts.append({
            "title": a.title,
            "url": a.url,
            "source": a.source_name,
            "topic": a.topic,
            "summary": a.summary[:300] if a.summary else "",
            "published_at": a.published_at or "unknown",
            "score": a.score,
        })
    return json.dumps(article_dicts, indent=2, ensure_ascii=False)


def _synthesize(articles: list[Article], prompt_template: str, date_str: str, day_str: str) -> Optional[dict]:
    """
    Core synthesis function: sends articles + prompt to Gemini and returns parsed JSON.

    Tries up to MAX_RETRIES times, waiting RETRY_DELAY seconds between attempts.

    Args:
        articles: Trimmed list of Article objects
        prompt_template: Either WEEKDAY_PROMPT or WEEKEND_PROMPT
        date_str: e.g. "March 28, 2026"
        day_str: e.g. "Friday"

    Returns:
        Parsed digest dict, or None if all retries fail
    """
    client = _get_client()
    if not client:
        return None

    model = _find_working_model(client)
    if not model:
        logger.error("Gemini: no working model found after trying all candidates")
        return None

    articles_json = _articles_to_json_string(articles)
    prompt = prompt_template.format(
        articles_json=articles_json,
        date=date_str,
        day_of_week=day_str,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(f"Gemini: synthesizing (attempt {attempt}/{MAX_RETRIES}, model={model})")
        text = _call_model(client, model, prompt)
        if text:
            result = _extract_json_from_response(text)
            if result:
                logger.info("Gemini: synthesis successful")
                return result
            logger.warning(f"Gemini: response received but JSON parse failed (attempt {attempt})")
        if attempt < MAX_RETRIES:
            logger.info(f"Gemini: retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

    logger.error(f"Gemini: all {MAX_RETRIES} attempts failed")
    return None


def synthesize_weekday(articles: list[Article], today: datetime) -> Optional[dict]:
    """
    Synthesize a weekday digest. Called Monday–Friday.

    Args:
        articles: Trimmed articles (max 10/section)
        today: Today's date in IST

    Returns:
        Structured digest dict, or None
    """
    logger.info(f"Gemini: weekday synthesis for {today.strftime('%Y-%m-%d')} with {len(articles)} articles")
    return _synthesize(
        articles,
        WEEKDAY_PROMPT,
        date_str=today.strftime("%B %d, %Y"),
        day_str=today.strftime("%A"),
    )


def synthesize_weekend(articles: list[Article], today: datetime) -> Optional[dict]:
    """
    Synthesize a weekly roundup. Called on Saturdays.

    Args:
        articles: Articles from the past week
        today: Today's date (Saturday) in IST

    Returns:
        Structured weekly digest dict, or None
    """
    logger.info(f"Gemini: weekend synthesis for {today.strftime('%Y-%m-%d')} with {len(articles)} articles")
    return _synthesize(
        articles,
        WEEKEND_PROMPT,
        date_str=today.strftime("%B %d, %Y"),
        day_str="Saturday",
    )


def generate_fallback_digest(articles: list[Article], today: datetime) -> dict:
    """
    Generate a minimal digest from raw articles when Gemini is unavailable.

    Groups articles by topic and formats them as plain headline lists.
    The HTML generator will show a warning banner when is_fallback=True.

    Args:
        articles: All collected articles
        today: Today's date

    Returns:
        Digest dict compatible with the daily.html template
    """
    from collections import defaultdict

    by_topic: dict[str, list[Article]] = defaultdict(list)
    for article in articles:
        by_topic[article.topic].append(article)

    sections = {}
    for topic, meta in SECTION_META.items():
        topic_articles = by_topic.get(topic, [])
        stories = [
            {
                "title": a.title,
                "summary": a.summary or "No summary available.",
                "source_url": a.url,
                "source_name": a.source_name,
            }
            for a in topic_articles[:4]
        ]
        sections[topic] = {
            "section_title": meta["title"],
            "stories": stories,
            "synthesis": "AI synthesis unavailable — showing raw headlines.",
        }

    all_sorted = sorted(articles, key=lambda a: a.score or 0, reverse=True)
    top_3 = [
        {
            "headline": a.title,
            "summary": a.summary[:200] if a.summary else "No summary available.",
            "section": a.topic,
            "source_url": a.url,
            "importance": "high",
        }
        for a in all_sorted[:3]
    ]

    return {
        "date": today.strftime("%B %d, %Y"),
        "day_of_week": today.strftime("%A"),
        "edition": "weekday",
        "is_fallback": True,
        "top_3": top_3,
        "sections": sections,
    }
