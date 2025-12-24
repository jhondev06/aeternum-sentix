"""
Aggregate - Aggregation of sentiment scores into time buckets.

This module builds sentiment bars by aggregating article-level sentiment
into ticker-time bucket features with various statistical measures.
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import yaml
import numpy as np
from datetime import datetime
import logging

from sentiment.finbert import FinBertSentiment

logger = logging.getLogger(__name__)

# Type aliases
SentimentBar = Dict[str, Any]


def build_sentiment_bars(
    articles_csv: str,
    window: str,
    config_path: str
) -> pd.DataFrame:
    """
    Build aggregated sentiment bars from article data.
    
    This function:
    1. Loads articles from CSV
    2. Runs FinBERT sentiment analysis on each article
    3. Aggregates sentiment scores into time buckets per ticker
    4. Computes statistical features for each bucket
    
    Args:
        articles_csv: Path to CSV file with article data.
                     Required columns: ticker, published_at, title, body
        window: Pandas frequency string for time buckets (e.g., 'W-MON', '1D').
        config_path: Path to config.yml with sentiment model settings.
        
    Returns:
        DataFrame with columns:
            - ticker: Ticker symbol
            - bucket_start: Start of time bucket (UTC)
            - mean_sent: Mean sentiment score
            - std_sent: Standard deviation of sentiment
            - min_sent: Minimum sentiment score
            - max_sent: Maximum sentiment score
            - count: Number of articles in bucket
            - unc_mean: Mean uncertainty (neutral probability)
            - time_decay_mean: Exponentially weighted mean
            
    Example:
        >>> bars = build_sentiment_bars(
        ...     'data/articles_raw.csv',
        ...     'W-MON',
        ...     'config.yml'
        ... )
    """
    # Load config
    config = _load_config(config_path)
    
    model_id: str = config['sentiment']['model_id']
    batch_size: int = config['sentiment']['batch_size']
    device: Optional[str] = config['sentiment'].get('device')
    half_life: int = config['aggregation']['decay_half_life']

    # Create FinBERT instance
    logger.info("Initializing FinBERT for sentiment analysis")
    finbert = FinBertSentiment(model_id, batch_size, device)

    # Read articles
    logger.info(f"Loading articles from {articles_csv}")
    df = pd.read_csv(articles_csv)
    df = _prepare_dataframe(df)
    
    if df.empty:
        logger.warning("No articles to process")
        return pd.DataFrame()

    # Create combined text for analysis
    df['text'] = df['title'].fillna('') + ' ' + df['body'].fillna('').str[:240]

    # Predict sentiment
    logger.info(f"Running sentiment analysis on {len(df)} articles")
    texts: List[str] = df['text'].tolist()
    sentiment_df = finbert.predict_batch(texts)
    df = pd.concat([df.reset_index(drop=True), sentiment_df], axis=1)

    # Floor to bucket
    df = _apply_bucket_floor(df, window)

    # Group and aggregate
    results = _aggregate_buckets(df, half_life)

    bars_df = pd.DataFrame(results)
    
    # Save to file
    output_path = 'data/sentiment_bars.csv'
    bars_df.to_csv(output_path, index=False)
    logger.info(f"Saved {len(bars_df)} sentiment bars to {output_path}")
    
    return bars_df


def _load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare DataFrame with proper datetime parsing."""
    df = df.copy()
    df['published_at'] = pd.to_datetime(df['published_at'], format='ISO8601', utc=True)
    return df


def _apply_bucket_floor(df: pd.DataFrame, window: str) -> pd.DataFrame:
    """Apply bucket flooring to timestamps."""
    df = df.copy()
    if 'W' in window:
        # Weekly buckets
        df['bucket_start'] = pd.to_datetime(
            df['published_at'].dt.to_period(window).dt.start_time,
            utc=True
        )
    else:
        # Other frequency buckets
        df['bucket_start'] = df['published_at'].dt.floor(window)
    return df


def _aggregate_buckets(df: pd.DataFrame, half_life: int) -> List[SentimentBar]:
    """
    Aggregate sentiment data into buckets.
    
    Args:
        df: DataFrame with sentiment scores and bucket_start.
        half_life: Half-life for exponential decay weighting.
        
    Returns:
        List of sentiment bar dictionaries.
    """
    grouped = df.groupby(['ticker', 'bucket_start'])
    results: List[SentimentBar] = []
    
    for (ticker, bucket), group in grouped:
        group = group.sort_values('published_at')
        scores = group.set_index('published_at')['score']
        neus = group['neu']

        # Time decay mean using exponential weighted average
        time_decay_mean: float
        if len(scores) > 0:
            try:
                time_decay_mean = float(scores.ewm(halflife=half_life).mean().iloc[-1])
            except Exception:
                time_decay_mean = float(scores.mean())
        else:
            time_decay_mean = np.nan

        result: SentimentBar = {
            'ticker': ticker,
            'bucket_start': bucket,
            'mean_sent': float(scores.mean()) if len(scores) > 0 else np.nan,
            'std_sent': float(scores.std()) if len(scores) > 1 else 0.0,
            'min_sent': float(scores.min()) if len(scores) > 0 else np.nan,
            'max_sent': float(scores.max()) if len(scores) > 0 else np.nan,
            'count': len(scores),
            'unc_mean': float(neus.mean()) if len(neus) > 0 else np.nan,
            'time_decay_mean': time_decay_mean
        }
        results.append(result)

    return results