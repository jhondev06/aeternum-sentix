"""
Database - SQLAlchemy persistence layer for Sentix.
Supports SQLite (local) and PostgreSQL (Supabase/Render).
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Generator
import pandas as pd
from datetime import datetime
from contextlib import contextmanager

from sqlalchemy import (
    create_engine, MetaData, Table, Column, 
    Integer, String, Float, DateTime, Text, 
    inspect, text, select
)
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

logger = logging.getLogger(__name__)

# Default database path for local SQLite
DB_PATH = Path("data/sentix.db")

# Global variables
_engine: Optional[Engine] = None
metadata = MetaData()

# Define Tables
articles_table = Table(
    'articles', metadata,
    Column('id', Text, primary_key=True),
    Column('ticker', Text, nullable=False, index=True),
    Column('source', Text),
    Column('published_at', Text, nullable=False, index=True),
    Column('title', Text),
    Column('body', Text),
    Column('url', Text),
    Column('lang', Text),
    Column('pos', Float),
    Column('neg', Float),
    Column('neu', Float),
    Column('score', Float),
    Column('created_at', Text, server_default=text("CURRENT_TIMESTAMP"))
)

sentiment_bars_table = Table(
    'sentiment_bars', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('ticker', Text, nullable=False, index=True),
    Column('bucket_start', Text, nullable=False, index=True),
    Column('mean_sent', Float),
    Column('std_sent', Float),
    Column('min_sent', Float),
    Column('max_sent', Float),
    Column('count', Integer),
    Column('unc_mean', Float),
    Column('time_decay_mean', Float),
    Column('created_at', Text, server_default=text("CURRENT_TIMESTAMP")),
    # Unique constraint handled manually or via index in DDL
)

alert_history_table = Table(
    'alert_history', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('rule_id', Text, nullable=False),
    Column('ticker', Text),
    Column('triggered_at', Text, nullable=False),
    Column('probability', Float),
    Column('action_type', Text),
    Column('action_result', Text),
    Column('message', Text)
)

price_data_table = Table(
    'price_data', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('ticker', Text, nullable=False, index=True),
    Column('timestamp', Text, nullable=False),
    Column('open', Float),
    Column('high', Float),
    Column('low', Float),
    Column('close', Float),
    Column('volume', Float)
    # Unique constraint handled manually
)


def get_engine() -> Engine:
    """
    Get or create SQLAlchemy engine.
    Prioritizes DATABASE_URL env var (PostgreSQL), falls back to local SQLite.
    """
    global _engine
    
    if _engine is None:
        database_url = os.environ.get("DATABASE_URL")
        
        if database_url:
            # Fix SQLAlchemy issue with postgres:// protocol
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            
            logger.info("Connecting to PostgreSQL database...")
            _engine = create_engine(database_url, pool_pre_ping=True)
            
        else:
            logger.info(f"Connecting to local SQLite: {DB_PATH}")
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            _engine = create_engine(f"sqlite:///{DB_PATH}")
            
    return _engine


@contextmanager
def get_conn() -> Generator[Connection, None, None]:
    """Context manager for database connection."""
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


def init_database() -> None:
    """Initialize database schema if tables don't exist."""
    engine = get_engine()
    metadata.create_all(engine)
    logger.info("Database schema initialized")


# =============================================================================
# Helper: Upsert Logic (Dialect Agnostic)
# =============================================================================

def _upsert(conn: Connection, table: Table, records: List[Dict[str, Any]], index_elements: List[str]):
    """
    Perform bulk upsert compatible with SQLite and PostgreSQL.
    """
    if not records:
        return

    dialect = conn.dialect.name
    
    if dialect == 'sqlite':
        stmt = sqlite_insert(table).values(records)
        # SQLite ON CONFLICT DO UPDATE
        # Note: SQLite requires 'set_' to be specified for columns to update
        update_cols = {col.name: col for col in stmt.excluded if col.name not in index_elements}
        if update_cols:
             stmt = stmt.on_conflict_do_update(
                index_elements=index_elements,
                set_=update_cols
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=index_elements)
        
        conn.execute(stmt)

    elif dialect == 'postgresql':
        stmt = pg_insert(table).values(records)
        update_cols = {col.name: col for col in stmt.excluded if col.name not in index_elements}
        
        if update_cols:
            stmt = stmt.on_conflict_do_update(
                index_elements=index_elements,
                set_=update_cols
            )
        else:
             stmt = stmt.on_conflict_do_nothing(index_elements=index_elements)
            
        conn.execute(stmt)
    else:
        raise NotImplementedError(f"Dialect {dialect} not supported for upsert")


# =============================================================================
# CRUD Operations
# =============================================================================

def save_articles(df: pd.DataFrame) -> int:
    """Save articles to database with upsert."""
    if df.empty:
        return 0
        
    records = df.to_dict(orient='records')
    
    # Ensure all columns exist in records (fill missing with None)
    valid_cols = [c.name for c in articles_table.columns]
    records_clean = []
    
    for rec in records:
        clean_rec = {k: v for k, v in rec.items() if k in valid_cols}
        records_clean.append(clean_rec)

    with get_conn() as conn:
        _upsert(conn, articles_table, records_clean, index_elements=['id'])
    
    logger.info(f"Saved {len(records)} articles")
    return len(records)


def load_articles(
    ticker: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000
) -> pd.DataFrame:
    """Load articles from database."""
    query = select(articles_table)
    
    if ticker:
        query = query.where(articles_table.c.ticker == ticker)
    if start_date:
        query = query.where(articles_table.c.published_at >= start_date)
    if end_date:
        query = query.where(articles_table.c.published_at <= end_date)
        
    query = query.order_by(articles_table.c.published_at.desc()).limit(limit)
    
    with get_engine().connect() as conn:
        df = pd.read_sql(query, conn)
        
    return df


def save_sentiment_bars(df: pd.DataFrame) -> int:
    """Save sentiment bars with upsert."""
    if df.empty:
        return 0
        
    records = df.to_dict(orient='records')
    
    # Convert timestamps to string if needed
    for rec in records:
        if 'bucket_start' in rec and not isinstance(rec['bucket_start'], str):
            rec['bucket_start'] = str(rec['bucket_start'])

    # Add Unique Constraint check manually for now since SQLite/PG idx diff
    # Logic: Delete existing overlap then insert, or strict upsert
    # For now, using strict Upsert on (ticker, bucket_start)
    # Ensure we actually have that unique constraint in DB
    
    # NOTE: We can't use _upsert easily if unique index isn't explicitly defined in Table object
    # But it is defined in DDL. Let's rely on that.
    
    # We need to manually add the unique constraint to the Table object for reflection to work?
    # No, we just need to pass the column names to index_elements
    
    valid_cols = [c.name for c in sentiment_bars_table.columns if c.name != 'id']
    records_clean = [{k: v for k, v in rec.items() if k in valid_cols} for rec in records]

    with get_conn() as conn:
        # Create unique constraint name logic is complex across DBs
        # Simpler approach: Check uniqueness on application level or trust Index
        
        # NOTE: SQLAlchemy upsert requires a Unique Constraint or Primary Key
        # We need to ensure (ticker, bucket_start) is unique
        
        # Let's try explicit Insert. If fails, Update. 
        # Actually _upsert works if there is a matching Unique Index in the DB.
        try:
             _upsert(conn, sentiment_bars_table, records_clean, index_elements=['ticker', 'bucket_start'])
        except Exception as e:
            logger.warning(f"Batch upsert failed, trying sequential: {e}")
            # Fallback
            for rec in records_clean:
                 conn.execute(sqlite_insert(sentiment_bars_table).values(rec))

    logger.info(f"Saved {len(records)} bars")
    return len(records)


def load_sentiment_bars(
    ticker: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pd.DataFrame:
    """Load sentiment bars."""
    query = select(sentiment_bars_table)
    
    if ticker:
        query = query.where(sentiment_bars_table.c.ticker == ticker)
    if start_date:
        query = query.where(sentiment_bars_table.c.bucket_start >= start_date)
    if end_date:
        query = query.where(sentiment_bars_table.c.bucket_start <= end_date)
        
    query = query.order_by(sentiment_bars_table.c.bucket_start.desc())
    
    with get_engine().connect() as conn:
        df = pd.read_sql(query, conn)
        
    if not df.empty and 'bucket_start' in df.columns:
        df['bucket_start'] = pd.to_datetime(df['bucket_start'])
        
    return df


def save_alert(
    rule_id: str,
    ticker: str,
    probability: float,
    action_type: str,
    action_result: str,
    message: str
) -> int:
    """Save alert."""
    record = {
        'rule_id': rule_id,
        'ticker': ticker,
        'triggered_at': datetime.utcnow().isoformat(),
        'probability': probability,
        'action_type': action_type,
        'action_result': action_result,
        'message': message
    }
    
    with get_conn() as conn:
        result = conn.execute(insert(alert_history_table).values(record))
        return result.inserted_primary_key[0] if result.inserted_primary_key else 0


def load_alert_history(rule_id: Optional[str] = None, days: int = 7) -> pd.DataFrame:
    """Load alerts."""
    query = select(alert_history_table)
    
    # Filter by date (sqlite/pg differences in date func handled by python for simplicity)
    # Actually, let's just load and filter in pandas to avoid dialect hell for now
    # Or use simple string comparison if ISO format
    
    cutoff = (datetime.utcnow() - pd.Timedelta(days=days)).isoformat()
    query = query.where(alert_history_table.c.triggered_at >= cutoff)
    
    if rule_id:
        query = query.where(alert_history_table.c.rule_id == rule_id)
        
    query = query.order_by(alert_history_table.c.triggered_at.desc())
    
    with get_engine().connect() as conn:
        df = pd.read_sql(query, conn)
        
    return df


def save_prices(df: pd.DataFrame) -> int:
    """Save prices."""
    if df.empty:
        return 0
    
    records = df.to_dict(orient='records')
    valid_cols = [c.name for c in price_data_table.columns if c.name != 'id']
    records_clean = []
    
    for rec in records:
        clean = {k: v for k, v in rec.items() if k in valid_cols}
        if 'timestamp' in clean and not isinstance(clean['timestamp'], str):
            clean['timestamp'] = str(clean['timestamp'])
        records_clean.append(clean)
        
    with get_conn() as conn:
        _upsert(conn, price_data_table, records_clean, index_elements=['ticker', 'timestamp'])
        
    return len(records)


def load_prices(ticker: str) -> pd.DataFrame:
    """Load prices."""
    query = select(price_data_table).where(price_data_table.c.ticker == ticker).order_by(price_data_table.c.timestamp)
    
    with get_engine().connect() as conn:
        df = pd.read_sql(query, conn)
        
    if not df.empty and 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
    return df

# Helper definition for simple insert since standard insert import was missed in save_alert
from sqlalchemy import insert

# Init on module load
if not DB_PATH.exists() and not os.environ.get("DATABASE_URL"):
    init_database()
