"""
RSS Client - Fetches news articles from RSS feeds.

This module provides functionality to ingest articles from multiple RSS feeds,
with language detection, deduplication, and content filtering.
"""

from typing import List, Set, Dict, Any, Optional
import feedparser
import pandas as pd
from langdetect import detect, LangDetectException
import hashlib
import time
from datetime import datetime
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

logger = logging.getLogger(__name__)


def fetch_rss(
    feeds: List[str],
    min_chars: int = 120,
    allowed_langs: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Fetch articles from multiple RSS feeds with filtering and deduplication.
    
    Args:
        feeds: List of RSS feed URLs to fetch from.
        min_chars: Minimum character count for title + body to include article.
        allowed_langs: List of allowed language codes (e.g., ['pt', 'en']).
                      If None, all languages are allowed.
    
    Returns:
        DataFrame with columns: id, source, published_at, title, body, url, lang
        
    Raises:
        No exceptions raised - failed feeds are logged and skipped.
    
    Example:
        >>> df = fetch_rss(
        ...     feeds=["https://example.com/rss"],
        ...     min_chars=100,
        ...     allowed_langs=["pt", "en"]
        ... )
    """
    if allowed_langs is None:
        allowed_langs = []
    
    articles: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    for feed_url in feeds:
        feed = _fetch_single_feed(feed_url)
        if feed is None or not feed.entries:
            continue

        domain = urlparse(feed_url).netloc
        
        for entry in feed.entries:
            article = _process_entry(
                entry=entry,
                domain=domain,
                min_chars=min_chars,
                allowed_langs=allowed_langs,
                seen_ids=seen_ids
            )
            if article is not None:
                articles.append(article)
                seen_ids.add(article['id'])

    logger.info(f"Fetched {len(articles)} articles from {len(feeds)} feeds")
    return pd.DataFrame(articles)


def _fetch_single_feed(feed_url: str, max_retries: int = 3) -> Optional[Any]:
    """
    Fetch a single RSS feed with retry logic.
    
    Args:
        feed_url: URL of the RSS feed.
        max_retries: Maximum number of retry attempts.
        
    Returns:
        Parsed feed object or None if all retries failed.
    """
    for attempt in range(max_retries):
        try:
            feed = feedparser.parse(feed_url)
            return feed
        except Exception as e:
            if attempt == max_retries - 1:
                logger.warning(f"Failed to fetch {feed_url} after {max_retries} attempts: {e}")
                return None
            time.sleep(1)  # Simple backoff
    return None


def _process_entry(
    entry: Any,
    domain: str,
    min_chars: int,
    allowed_langs: List[str],
    seen_ids: Set[str]
) -> Optional[Dict[str, Any]]:
    """
    Process a single RSS entry into an article dict.
    
    Args:
        entry: RSS entry object from feedparser.
        domain: Domain of the RSS feed.
        min_chars: Minimum character count.
        allowed_langs: List of allowed language codes.
        seen_ids: Set of already seen article IDs for deduplication.
        
    Returns:
        Article dict or None if entry should be skipped.
    """
    title: str = entry.get('title', '') or ''
    summary: str = entry.get('summary', '') or ''
    body: str = summary
    url: str = entry.get('link', '') or ''

    # Combine title and body for checks
    text = title + body

    if len(text) < min_chars:
        return None

    # Language detection
    try:
        lang = detect(text)
        if allowed_langs and lang not in allowed_langs:
            return None
    except LangDetectException:
        logger.debug(f"Could not detect language for article: {title[:50]}")
        return None

    # Published timestamp
    published = entry.get('published_parsed')
    if published:
        timestamp = time.mktime(published)
        published_at = datetime.utcfromtimestamp(timestamp).isoformat() + 'Z'
    else:
        published_at = datetime.utcnow().isoformat() + 'Z'

    # Article ID: SHA1 of title + domain
    id_str = title + domain
    article_id = hashlib.sha1(id_str.encode('utf-8')).hexdigest()

    if article_id in seen_ids:
        return None

    return {
        'id': article_id,
        'source': domain,
        'published_at': published_at,
        'title': title,
        'body': body,
        'url': url,
        'lang': lang
    }