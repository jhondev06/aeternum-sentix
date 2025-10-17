#!/usr/bin/env python3
"""
Rebuild sentiment_bars.csv from articles_raw.csv
"""

import yaml
from features.aggregate import build_sentiment_bars

def rebuild_sentiment_bars():
    # Load config
    with open('config.yml', 'r') as f:
        config = yaml.safe_load(f)

    # Build sentiment bars
    print("Building sentiment bars from articles_raw.csv...")
    sentiment_df = build_sentiment_bars('data/articles_raw.csv', config['aggregation']['window'], 'config.yml')

    # Save to sentiment_bars.csv
    sentiment_df.to_csv('data/sentiment_bars.csv', index=False)
    print(f"Sentiment bars saved with {len(sentiment_df)} records")
    print("Unique tickers:", sentiment_df['ticker'].unique())

if __name__ == "__main__":
    rebuild_sentiment_bars()