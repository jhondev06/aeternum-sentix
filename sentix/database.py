"""
Database - SQLite persistence layer for Sentix.

This module provides a centralized database interface for storing
articles, sentiment bars, and alert history.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Dict, Any, Optional, Generator
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Default database path
DB_PATH = Path("data/sentix.db")


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Get a database connection.
    
    Args:
        db_path: Optional path to database file. Uses default if None.
        
    Returns:
        SQLite connection object.
    """
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database connections.
    
    Args:
        db_path: Optional path to database file.
        
    Yields:
        SQLite connection that auto-commits on success.
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database(db_path: Optional[Path] = None) -> None:
    """
    Initialize database schema.
    
    Creates tables if they don't exist:
    - articles: Raw ingested articles
    - sentiment_bars: Aggregated sentiment data
    - alert_history: Triggered alerts log
    - price_data: Historical price data
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        
        # Articles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                source TEXT,
                published_at TEXT NOT NULL,
                title TEXT,
                body TEXT,
                url TEXT,
                lang TEXT,
                pos REAL,
                neg REAL,
                neu REAL,
                score REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Sentiment bars table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sentiment_bars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                bucket_start TEXT NOT NULL,
                mean_sent REAL,
                std_sent REAL,
                min_sent REAL,
                max_sent REAL,
                count INTEGER,
                unc_mean REAL,
                time_decay_mean REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, bucket_start)
            )
        """)
        
        # Alert history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id TEXT NOT NULL,
                ticker TEXT,
                triggered_at TEXT NOT NULL,
                probability REAL,
                action_type TEXT,
                action_result TEXT,
                message TEXT
            )
        """)
        
        # Price data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                UNIQUE(ticker, timestamp)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_ticker ON articles(ticker)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bars_ticker ON sentiment_bars(ticker)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bars_bucket ON sentiment_bars(bucket_start)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_ticker ON price_data(ticker)")
        
        logger.info("Database schema initialized")


# =============================================================================
# Articles CRUD
# =============================================================================

def save_articles(df: pd.DataFrame, db_path: Optional[Path] = None) -> int:
    """
    Save articles DataFrame to database.
    
    Args:
        df: DataFrame with article data.
        db_path: Optional database path.
        
    Returns:
        Number of rows inserted.
    """
    if df.empty:
        return 0
    
    with get_db(db_path) as conn:
        # Prepare columns
        columns = ['id', 'ticker', 'source', 'published_at', 'title', 'body', 'url', 'lang']
        if 'pos' in df.columns:
            columns.extend(['pos', 'neg', 'neu', 'score'])
        
        available_cols = [c for c in columns if c in df.columns]
        df_insert = df[available_cols].copy()
        
        # Insert with REPLACE to handle duplicates
        placeholders = ', '.join(['?' for _ in available_cols])
        cols_str = ', '.join(available_cols)
        
        cursor = conn.cursor()
        rows_inserted = 0
        
        for _, row in df_insert.iterrows():
            try:
                cursor.execute(
                    f"INSERT OR REPLACE INTO articles ({cols_str}) VALUES ({placeholders})",
                    tuple(row[col] for col in available_cols)
                )
                rows_inserted += 1
            except sqlite3.Error as e:
                logger.warning(f"Error inserting article {row.get('id', 'unknown')}: {e}")
        
        logger.info(f"Saved {rows_inserted} articles to database")
        return rows_inserted


def load_articles(
    ticker: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000,
    db_path: Optional[Path] = None
) -> pd.DataFrame:
    """
    Load articles from database.
    
    Args:
        ticker: Filter by ticker.
        start_date: Filter by start date (ISO format).
        end_date: Filter by end date (ISO format).
        limit: Maximum rows to return.
        db_path: Optional database path.
        
    Returns:
        DataFrame with articles.
    """
    query = "SELECT * FROM articles WHERE 1=1"
    params: List[Any] = []
    
    if ticker:
        query += " AND ticker = ?"
        params.append(ticker)
    if start_date:
        query += " AND published_at >= ?"
        params.append(start_date)
    if end_date:
        query += " AND published_at <= ?"
        params.append(end_date)
    
    query += f" ORDER BY published_at DESC LIMIT {limit}"
    
    with get_db(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)
    
    return df


# =============================================================================
# Sentiment Bars CRUD
# =============================================================================

def save_sentiment_bars(df: pd.DataFrame, db_path: Optional[Path] = None) -> int:
    """
    Save sentiment bars DataFrame to database.
    
    Args:
        df: DataFrame with sentiment bar data.
        db_path: Optional database path.
        
    Returns:
        Number of rows inserted.
    """
    if df.empty:
        return 0
    
    columns = ['ticker', 'bucket_start', 'mean_sent', 'std_sent', 'min_sent', 
               'max_sent', 'count', 'unc_mean', 'time_decay_mean']
    
    available_cols = [c for c in columns if c in df.columns]
    df_insert = df[available_cols].copy()
    
    # Convert timestamps to string
    if 'bucket_start' in df_insert.columns:
        df_insert['bucket_start'] = df_insert['bucket_start'].astype(str)
    
    with get_db(db_path) as conn:
        placeholders = ', '.join(['?' for _ in available_cols])
        cols_str = ', '.join(available_cols)
        
        cursor = conn.cursor()
        rows_inserted = 0
        
        for _, row in df_insert.iterrows():
            try:
                cursor.execute(
                    f"INSERT OR REPLACE INTO sentiment_bars ({cols_str}) VALUES ({placeholders})",
                    tuple(row[col] for col in available_cols)
                )
                rows_inserted += 1
            except sqlite3.Error as e:
                logger.warning(f"Error inserting bar: {e}")
        
        logger.info(f"Saved {rows_inserted} sentiment bars to database")
        return rows_inserted


def load_sentiment_bars(
    ticker: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Optional[Path] = None
) -> pd.DataFrame:
    """
    Load sentiment bars from database.
    
    Args:
        ticker: Filter by ticker.
        start_date: Filter by start bucket.
        end_date: Filter by end bucket.
        db_path: Optional database path.
        
    Returns:
        DataFrame with sentiment bars.
    """
    query = "SELECT * FROM sentiment_bars WHERE 1=1"
    params: List[Any] = []
    
    if ticker:
        query += " AND ticker = ?"
        params.append(ticker)
    if start_date:
        query += " AND bucket_start >= ?"
        params.append(start_date)
    if end_date:
        query += " AND bucket_start <= ?"
        params.append(end_date)
    
    query += " ORDER BY bucket_start DESC"
    
    with get_db(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)
    
    if not df.empty and 'bucket_start' in df.columns:
        df['bucket_start'] = pd.to_datetime(df['bucket_start'])
    
    return df


# =============================================================================
# Alert History CRUD
# =============================================================================

def save_alert(
    rule_id: str,
    ticker: str,
    probability: float,
    action_type: str,
    action_result: str,
    message: str,
    db_path: Optional[Path] = None
) -> int:
    """
    Save an alert to history.
    
    Returns:
        ID of inserted row.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO alert_history 
               (rule_id, ticker, triggered_at, probability, action_type, action_result, message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (rule_id, ticker, datetime.utcnow().isoformat(), probability, 
             action_type, action_result, message)
        )
        return cursor.lastrowid


def load_alert_history(
    rule_id: Optional[str] = None,
    days: int = 7,
    db_path: Optional[Path] = None
) -> pd.DataFrame:
    """
    Load alert history from database.
    
    Args:
        rule_id: Filter by rule ID.
        days: Load last N days.
        db_path: Optional database path.
        
    Returns:
        DataFrame with alert history.
    """
    query = f"""
        SELECT * FROM alert_history 
        WHERE triggered_at >= datetime('now', '-{days} days')
    """
    params: List[Any] = []
    
    if rule_id:
        query += " AND rule_id = ?"
        params.append(rule_id)
    
    query += " ORDER BY triggered_at DESC"
    
    with get_db(db_path) as conn:
        return pd.read_sql_query(query, conn, params=params)


# =============================================================================
# Price Data CRUD
# =============================================================================

def save_prices(df: pd.DataFrame, db_path: Optional[Path] = None) -> int:
    """
    Save price data to database.
    
    Args:
        df: DataFrame with OHLCV data.
        db_path: Optional database path.
        
    Returns:
        Number of rows inserted.
    """
    if df.empty:
        return 0
    
    columns = ['ticker', 'timestamp', 'open', 'high', 'low', 'close', 'volume']
    available_cols = [c for c in columns if c in df.columns]
    df_insert = df[available_cols].copy()
    
    if 'timestamp' in df_insert.columns:
        df_insert['timestamp'] = df_insert['timestamp'].astype(str)
    
    with get_db(db_path) as conn:
        placeholders = ', '.join(['?' for _ in available_cols])
        cols_str = ', '.join(available_cols)
        
        cursor = conn.cursor()
        rows_inserted = 0
        
        for _, row in df_insert.iterrows():
            try:
                cursor.execute(
                    f"INSERT OR REPLACE INTO price_data ({cols_str}) VALUES ({placeholders})",
                    tuple(row[col] for col in available_cols)
                )
                rows_inserted += 1
            except sqlite3.Error as e:
                logger.warning(f"Error inserting price: {e}")
        
        return rows_inserted


def load_prices(
    ticker: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Optional[Path] = None
) -> pd.DataFrame:
    """
    Load price data from database.
    """
    query = "SELECT * FROM price_data WHERE ticker = ?"
    params: List[Any] = [ticker]
    
    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)
    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date)
    
    query += " ORDER BY timestamp"
    
    with get_db(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)
    
    if not df.empty and 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    return df


# =============================================================================
# Migration from CSV
# =============================================================================

def migrate_from_csv(data_dir: str = "data", db_path: Optional[Path] = None) -> Dict[str, int]:
    """
    Migrate existing CSV files to SQLite database.
    
    Args:
        data_dir: Directory containing CSV files.
        db_path: Optional database path.
        
    Returns:
        Dictionary with migration statistics.
    """
    data_path = Path(data_dir)
    stats = {'articles': 0, 'sentiment_bars': 0, 'prices': 0}
    
    # Initialize schema
    init_database(db_path)
    
    # Migrate articles
    articles_csv = data_path / "articles_raw.csv"
    if articles_csv.exists():
        df = pd.read_csv(articles_csv)
        stats['articles'] = save_articles(df, db_path)
        logger.info(f"Migrated {stats['articles']} articles from CSV")
    
    # Migrate sentiment bars
    bars_csv = data_path / "sentiment_bars.csv"
    if bars_csv.exists():
        df = pd.read_csv(bars_csv)
        stats['sentiment_bars'] = save_sentiment_bars(df, db_path)
        logger.info(f"Migrated {stats['sentiment_bars']} sentiment bars from CSV")
    
    # Migrate demo prices
    prices_csv = data_path / "demo_prices.csv"
    if prices_csv.exists():
        df = pd.read_csv(prices_csv)
        if 'date' in df.columns:
            df = df.rename(columns={'date': 'timestamp'})
        stats['prices'] = save_prices(df, db_path)
        logger.info(f"Migrated {stats['prices']} price records from CSV")
    
    return stats


# Initialize on import if database doesn't exist
if not DB_PATH.exists():
    init_database()
