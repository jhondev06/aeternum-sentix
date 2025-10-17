import tweepy
import pandas as pd
from langdetect import detect
import hashlib
from datetime import datetime
import time

class TwitterClient:
    def __init__(self, api_key: str, api_secret: str, access_token: str, access_token_secret: str, bearer_token: str):
        self.client = tweepy.Client(
            bearer_token=bearer_token,
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )

    def fetch_tweets(self, query: str, max_results: int = 100, hours_back: int = 24) -> pd.DataFrame:
        tweets = []
        seen_ids = set()

        # Build query with time filter
        start_time = datetime.utcnow() - pd.Timedelta(hours=hours_back)
        query_with_time = f"{query} -is:retweet lang:pt"

        try:
            response = self.client.search_recent_tweets(
                query=query_with_time,
                start_time=start_time,
                max_results=max_results,
                tweet_fields=['created_at', 'public_metrics', 'lang', 'text']
            )

            if response.data:
                for tweet in response.data:
                    # Skip if already seen
                    tweet_id = str(tweet.id)
                    if tweet_id in seen_ids:
                        continue
                    seen_ids.add(tweet_id)

                    # Detect language
                    try:
                        lang = detect(tweet.text)
                        if lang not in ['pt', 'en']:
                            continue
                    except:
                        continue

                    # Create article-like entry
                    tweets.append({
                        'id': hashlib.sha1(tweet_id.encode()).hexdigest(),
                        'source': 'Twitter',
                        'published_at': tweet.created_at.isoformat() + 'Z',
                        'title': tweet.text[:100] + '...' if len(tweet.text) > 100 else tweet.text,
                        'body': tweet.text,
                        'url': f"https://twitter.com/i/status/{tweet.id}",
                        'lang': lang
                    })

        except tweepy.TweepyException as e:
            print(f"Twitter API error: {e}")

        return pd.DataFrame(tweets)

def fetch_twitter_data(api_key: str, api_secret: str, access_token: str, access_token_secret: str,
                      bearer_token: str, tickers: list, max_results: int = 50) -> pd.DataFrame:
    client = TwitterClient(api_key, api_secret, access_token, access_token_secret, bearer_token)

    all_tweets = []
    for ticker in tickers:
        # Search for ticker mentions
        query = f'"{ticker}" OR "{ticker.replace(".SA", "")}"'
        tweets = client.fetch_tweets(query, max_results=max_results // len(tickers))
        all_tweets.append(tweets)

    if all_tweets:
        return pd.concat(all_tweets, ignore_index=True)
    return pd.DataFrame()