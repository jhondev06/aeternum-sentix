"""
Label - Create training labels by aligning sentiment data with price movements.

This module handles the creation of training datasets by merging sentiment
bars with price data and computing forward returns as labels.
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def make_labels(
    sent_bars_csv: str,
    horizon_bars: int,
    price_cfg: Dict[str, Any]
) -> pd.DataFrame:
    """
    Create labeled training data by merging sentiment bars with price data.
    
    This function:
    1. Loads sentiment bars from CSV
    2. Downloads/loads price data for configured symbols
    3. Merges sentiment with prices on (ticker, bucket_start)
    4. Computes forward returns and binary labels
    
    Args:
        sent_bars_csv: Path to sentiment bars CSV file.
        horizon_bars: Number of buckets ahead for forward return calculation.
        price_cfg: Price configuration dict with keys:
            - symbols: List of ticker symbols
            - interval: Price data interval (e.g., '1d')
            - period: Historical period (e.g., '1y')
            
    Returns:
        DataFrame with sentiment features, price data, and labels:
            - All sentiment bar columns
            - close: Current close price
            - close_fwd: Forward close price
            - r_fwd: Forward return
            - y: Binary label (1 if r_fwd > 0)
            
    Example:
        >>> training_df = make_labels(
        ...     'data/sentiment_bars.csv',
        ...     horizon_bars=1,
        ...     price_cfg={'symbols': ['PETR4.SA'], 'interval': '1d', 'period': '1y'}
        ... )
    """
    # Read sentiment bars
    logger.info(f"Loading sentiment bars from {sent_bars_csv}")
    sent_df = pd.read_csv(sent_bars_csv)
    sent_df['bucket_start'] = pd.to_datetime(sent_df['bucket_start'], utc=True)

    # Load price data
    prices_df = _load_price_data(price_cfg)
    
    if prices_df.empty:
        logger.error("No price data available")
        return pd.DataFrame()

    # Resample to weekly, taking last close of the week
    prices_weekly = _resample_prices_weekly(prices_df)

    # Merge sentiment with prices
    merged = pd.merge(
        sent_df,
        prices_weekly,
        on=['ticker', 'bucket_start'],
        how='inner'
    )
    
    logger.info(f"Merged {len(merged)} rows (sentiment + prices)")

    if merged.empty:
        logger.warning("No matching data after merge")
        return pd.DataFrame()

    # Compute forward return and labels
    merged = _compute_labels(merged, horizon_bars)

    # Save to file
    output_path = 'data/training_set.csv'
    merged.to_csv(output_path, index=False)
    logger.info(f"Saved training set to {output_path}")
    
    return merged


def _load_price_data(price_cfg: Dict[str, Any]) -> pd.DataFrame:
    """
    Load price data from yfinance or fallback to demo data.
    
    Args:
        price_cfg: Price configuration dictionary.
        
    Returns:
        DataFrame with columns: ticker, timestamp, close
    """
    symbols: List[str] = price_cfg.get('symbols', [])
    interval: str = price_cfg.get('interval', '1d')
    period: str = price_cfg.get('period', '1y')

    prices_df_list: List[pd.DataFrame] = []
    
    try:
        import yfinance as yf
        
        for sym in symbols:
            # Skip non-tradeable indices
            if sym in ['IPCA', 'PIB', 'SELIC']:
                continue
                
            logger.info(f"Downloading price data for {sym}")
            data = yf.download(sym, interval=interval, period=period, progress=False)
            
            if not isinstance(data, pd.DataFrame) or data.empty:
                logger.warning(f"No data downloaded for {sym}")
                continue
                
            data = data.reset_index()
            
            # Flatten MultiIndex columns if present
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.droplevel(1)
            
            # Determine date column name
            date_col = _find_date_column(data.columns)
            if date_col is None:
                logger.warning(f"Could not find date column for {sym}")
                continue
                
            data[date_col] = pd.to_datetime(data[date_col])
            data['ticker'] = sym
            data.rename(columns={'Close': 'close', date_col: 'timestamp'}, inplace=True)
            
            # Make timezone aware (UTC)
            if data['timestamp'].dt.tz is None:
                data['timestamp'] = data['timestamp'].dt.tz_localize('UTC')
            else:
                data['timestamp'] = data['timestamp'].dt.tz_convert('UTC')
                
            prices_df_list.append(data[['ticker', 'timestamp', 'close']])
            
        if prices_df_list:
            return pd.concat(prices_df_list, ignore_index=True)
            
    except ImportError:
        logger.warning("yfinance not available, using demo prices")
    except Exception as e:
        logger.warning(f"Error downloading prices: {e}, falling back to demo data")
    
    # Fallback to demo prices
    return _load_demo_prices()


def _find_date_column(columns: pd.Index) -> Optional[str]:
    """Find the date column name in a DataFrame."""
    for col in ['Datetime', 'Date']:
        if col in columns:
            return col
    return None


def _load_demo_prices() -> pd.DataFrame:
    """Load demo prices from CSV fallback."""
    try:
        prices_df = pd.read_csv('data/demo_prices.csv')
        prices_df['timestamp'] = pd.to_datetime(prices_df['date']).dt.tz_localize('UTC')
        prices_df = prices_df.rename(columns={'ticker': 'ticker', 'close': 'close'})
        return prices_df[['ticker', 'timestamp', 'close']]
    except FileNotFoundError:
        logger.error("Demo prices file not found: data/demo_prices.csv")
        return pd.DataFrame()


def _resample_prices_weekly(prices_df: pd.DataFrame) -> pd.DataFrame:
    """
    Resample prices to weekly frequency.
    
    Args:
        prices_df: DataFrame with ticker, timestamp, close.
        
    Returns:
        DataFrame with ticker, bucket_start, close.
    """
    prices_weekly = (
        prices_df
        .set_index('timestamp')
        .groupby('ticker')
        .resample('W-MON', label='left', closed='left')['close']
        .last()
        .reset_index()
    )
    prices_weekly = prices_weekly.rename(columns={'timestamp': 'bucket_start'})
    return prices_weekly


def _compute_labels(df: pd.DataFrame, horizon_bars: int) -> pd.DataFrame:
    """
    Compute forward returns and binary labels.
    
    Args:
        df: Merged DataFrame with prices.
        horizon_bars: Number of bars for forward return.
        
    Returns:
        DataFrame with r_fwd and y columns added.
    """
    df = df.sort_values(['ticker', 'bucket_start']).copy()
    df['close_fwd'] = df.groupby('ticker')['close'].shift(-horizon_bars)
    df['r_fwd'] = (df['close_fwd'] / df['close']) - 1
    df['y'] = (df['r_fwd'] > 0).astype(int)

    # Drop rows with NaN r_fwd (last horizon_bars rows per ticker)
    before_count = len(df)
    df = df.dropna(subset=['r_fwd'])
    logger.info(f"Dropped {before_count - len(df)} rows with NaN forward returns")
    
    return df