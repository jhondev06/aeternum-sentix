import feedparser
import pandas as pd
from langdetect import detect
import hashlib
import time
from datetime import datetime
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def fetch_rss(feeds: list[str], min_chars: int, allowed_langs: list[str]) -> pd.DataFrame:
    articles = []
    seen_ids = set()

    for feed_url in feeds:
        for attempt in range(3):  # retry up to 2 times (attempt 0,1,2)
            try:
                feed = feedparser.parse(feed_url)
                break
            except Exception as e:
                if attempt == 2:
                    print(f"Failed to fetch {feed_url} after 3 attempts: {e}")
                    continue
                time.sleep(1)  # simple backoff

        if not feed.entries:
            continue

        domain = urlparse(feed_url).netloc

        for entry in feed.entries:
            title = entry.get('title', '')
            summary = entry.get('summary', '')
            body = summary if summary else ''
            url = entry.get('link', '')

            # Combine title and body for checks
            text = (title or '') + (body or '')

            if len(text) < min_chars:
                continue

            try:
                lang = detect(text)
                if lang not in allowed_langs:
                    continue
            except:
                continue  # skip if lang detect fails

            # Published at
            published = entry.get('published_parsed')
            if published:
                timestamp = time.mktime(published)
                published_at = datetime.utcfromtimestamp(timestamp).isoformat() + 'Z'
            else:
                published_at = datetime.utcnow().isoformat() + 'Z'

            # ID: sha1 of title + domain
            id_str = (title or '') + domain
            article_id = hashlib.sha1(id_str.encode('utf-8')).hexdigest()

            if article_id in seen_ids:
                continue
            seen_ids.add(article_id)

            articles.append({
                'id': article_id,
                'source': domain,
                'published_at': published_at,
                'title': title,
                'body': body,
                'url': url,
                'lang': lang
            })

    return pd.DataFrame(articles)