"""
Normalize - Text normalization and ticker entity mapping.

This module handles loading ticker configurations and mapping
text mentions to standardized ticker symbols.
"""

from typing import Dict, List, Any, Optional
import yaml
import re
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Type aliases for clarity
TickerMap = Dict[str, Dict[str, List[str]]]
CompiledRegexMap = Dict[str, re.Pattern]


def load_ticker_map(yaml_path: str) -> TickerMap:
    """
    Load ticker alias mapping from YAML file.
    
    Args:
        yaml_path: Path to the tickers.yml configuration file.
        
    Returns:
        Dictionary mapping ticker symbols to their configuration,
        including aliases list.
        
    Raises:
        FileNotFoundError: If yaml_path doesn't exist.
        yaml.YAMLError: If YAML is malformed.
        
    Example:
        >>> ticker_map = load_ticker_map('tickers.yml')
        >>> ticker_map['PETR4.SA']['aliases']
        ['Petrobras', 'PETR4', 'B3:PETR4']
    """
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def _compile_ticker_patterns(ticker_map: TickerMap) -> CompiledRegexMap:
    """
    Compile regex patterns for each ticker's aliases.
    
    Args:
        ticker_map: Ticker configuration from load_ticker_map.
        
    Returns:
        Dictionary mapping ticker symbols to compiled regex patterns.
    """
    regex_map: CompiledRegexMap = {}
    for ticker, data in ticker_map.items():
        aliases = data.get('aliases', [])
        if not aliases:
            continue
        pattern = '|'.join(re.escape(alias) for alias in aliases)
        regex_map[ticker] = re.compile(pattern, re.IGNORECASE)
    return regex_map


def _find_tickers_in_text(text: str, regex_map: CompiledRegexMap) -> List[str]:
    """
    Find all matching tickers in a text string.
    
    Args:
        text: Text content to search.
        regex_map: Compiled regex patterns from _compile_ticker_patterns.
        
    Returns:
        List of matching ticker symbols.
    """
    matches: List[str] = []
    for ticker, regex in regex_map.items():
        if regex.search(text):
            matches.append(ticker)
    return matches


def map_entities(df: pd.DataFrame, ticker_map: TickerMap) -> pd.DataFrame:
    """
    Map article text to ticker entities using alias matching.
    
    This function:
    1. Searches for ticker aliases in title and body
    2. Adds a 'tickers' column with matched tickers
    3. Explodes to one row per (article, ticker) pair
    4. Removes articles with no ticker matches
    
    Args:
        df: DataFrame with 'title' and 'body' columns.
        ticker_map: Ticker configuration from load_ticker_map.
        
    Returns:
        DataFrame with columns: id, ticker, published_at, title, body, 
        url, lang, source. One row per article-ticker pair.
        
    Example:
        >>> mapped_df = map_entities(articles_df, ticker_map)
        >>> mapped_df[['id', 'ticker']].head()
    """
    if df.empty:
        logger.warning("Empty DataFrame provided to map_entities")
        return pd.DataFrame(columns=[
            'id', 'ticker', 'published_at', 'title', 'body', 'url', 'lang', 'source'
        ])
    
    # Compile regex for each ticker
    regex_map = _compile_ticker_patterns(ticker_map)

    # Function to find matching tickers for a row
    def find_tickers(row: pd.Series) -> List[str]:
        title = row.get('title') or ''
        body = row.get('body') or ''
        
        # Handle potential None values
        if not isinstance(title, str):
            title = ''
        if not isinstance(body, str):
            body = ''
            
        text = title + ' ' + body
        return _find_tickers_in_text(text, regex_map)

    # Apply to each row
    df = df.copy()
    df['tickers'] = df.apply(find_tickers, axis=1)

    # Filter out rows with no tickers
    df = df[df['tickers'].apply(len) > 0]
    
    if df.empty:
        logger.warning("No articles matched any ticker aliases")
        return pd.DataFrame(columns=[
            'id', 'ticker', 'published_at', 'title', 'body', 'url', 'lang', 'source'
        ])

    # Explode to one row per article-ticker
    df = df.explode('tickers').rename(columns={'tickers': 'ticker'})

    # Keep only specified columns
    keep_cols = ['id', 'ticker', 'published_at', 'title', 'body', 'url', 'lang', 'source']
    available_cols = [col for col in keep_cols if col in df.columns]
    
    logger.info(f"Mapped {len(df)} article-ticker pairs")
    return df[available_cols]