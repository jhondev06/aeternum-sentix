import pandas as pd
import yaml
from sentiment.finbert import FinBertSentiment
import numpy as np
from datetime import datetime

def build_sentiment_bars(articles_csv: str, window: str, config_path: str) -> pd.DataFrame:
    # Load config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    model_id = config['sentiment']['model_id']
    batch_size = config['sentiment']['batch_size']
    device = config['sentiment'].get('device')
    half_life = config['aggregation']['decay_half_life']

    # Create FinBERT
    finbert = FinBertSentiment(model_id, batch_size, device)

    # Read articles
    df = pd.read_csv(articles_csv)
    df['published_at'] = pd.to_datetime(df['published_at'], format='ISO8601', utc=True)

    # Create texts
    df['text'] = df['title'].fillna('') + ' ' + df['body'].fillna('').str[:240]

    # Predict sentiment
    texts = df['text'].tolist()
    sentiment_df = finbert.predict_batch(texts)
    df = pd.concat([df, sentiment_df], axis=1)

    # Floor to bucket
    if 'W' in window:
        df['bucket_start'] = pd.to_datetime(df['published_at'].dt.to_period(window).dt.start_time, utc=True)
    else:
        df['bucket_start'] = df['published_at'].dt.floor(window)

    # Group and aggregate
    grouped = df.groupby(['ticker', 'bucket_start'])

    results = []
    for (ticker, bucket), group in grouped:
        group = group.sort_values('published_at')
        scores = group.set_index('published_at')['score']
        neus = group['neu']

        # Time decay mean
        time_decay_mean = scores.ewm(halflife=half_life).mean().iloc[-1] if len(scores) > 0 else np.nan

        result = {
            'ticker': ticker,
            'bucket_start': bucket,
            'mean_sent': scores.mean(),
            'std_sent': scores.std(),
            'min_sent': scores.min(),
            'max_sent': scores.max(),
            'count': len(scores),
            'unc_mean': neus.mean(),
            'time_decay_mean': time_decay_mean
        }
        results.append(result)

    bars_df = pd.DataFrame(results)
    bars_df.to_csv('data/sentiment_bars.csv', index=False)
    return bars_df