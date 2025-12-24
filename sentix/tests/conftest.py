"""
Pytest configuration and shared fixtures for Sentix tests.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import tempfile
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_articles_df() -> pd.DataFrame:
    """Create sample articles DataFrame for testing."""
    return pd.DataFrame({
        'id': ['abc123', 'def456', 'ghi789'],
        'source': ['test.com', 'test.com', 'news.com'],
        'published_at': [
            '2024-01-01T10:00:00Z',
            '2024-01-02T10:00:00Z',
            '2024-01-03T10:00:00Z'
        ],
        'title': [
            'Petrobras announces record profits',
            'Vale stock surges after earnings',
            'Itaú expands banking services'
        ],
        'body': [
            'The Brazilian oil company reported strong quarterly results',
            'Mining giant sees increased demand for iron ore',
            'Brazilian bank launches new digital platform'
        ],
        'url': ['https://test.com/1', 'https://test.com/2', 'https://news.com/3'],
        'lang': ['en', 'en', 'en']
    })


@pytest.fixture
def sample_ticker_map() -> dict:
    """Create sample ticker map for testing."""
    return {
        'PETR4.SA': {
            'aliases': ['Petrobras', 'PETR4', 'Brazilian oil']
        },
        'VALE3.SA': {
            'aliases': ['Vale', 'VALE3', 'Mining giant']
        },
        'ITUB4.SA': {
            'aliases': ['Itaú', 'ITUB4', 'Brazilian bank']
        }
    }


@pytest.fixture
def sample_sentiment_bars_df() -> pd.DataFrame:
    """Create sample sentiment bars DataFrame for testing."""
    return pd.DataFrame({
        'ticker': ['PETR4.SA', 'PETR4.SA', 'VALE3.SA'],
        'bucket_start': pd.to_datetime([
            '2024-01-01', '2024-01-08', '2024-01-01'
        ]).tz_localize('UTC'),
        'mean_sent': [0.3, -0.1, 0.5],
        'std_sent': [0.1, 0.2, 0.15],
        'min_sent': [0.1, -0.3, 0.3],
        'max_sent': [0.5, 0.1, 0.7],
        'count': [5, 3, 8],
        'unc_mean': [0.3, 0.4, 0.25],
        'time_decay_mean': [0.28, -0.08, 0.48]
    })


@pytest.fixture
def sample_training_df() -> pd.DataFrame:
    """Create sample training DataFrame for testing."""
    np.random.seed(42)
    n_samples = 50
    
    return pd.DataFrame({
        'ticker': np.random.choice(['PETR4.SA', 'VALE3.SA'], n_samples),
        'bucket_start': pd.date_range('2024-01-01', periods=n_samples, freq='W'),
        'mean_sent': np.random.uniform(-0.5, 0.5, n_samples),
        'std_sent': np.random.uniform(0, 0.3, n_samples),
        'min_sent': np.random.uniform(-0.8, 0, n_samples),
        'max_sent': np.random.uniform(0, 0.8, n_samples),
        'count': np.random.randint(1, 20, n_samples),
        'unc_mean': np.random.uniform(0.2, 0.5, n_samples),
        'time_decay_mean': np.random.uniform(-0.4, 0.4, n_samples),
        'close': np.random.uniform(20, 50, n_samples),
        'r_fwd': np.random.uniform(-0.1, 0.1, n_samples),
        'y': np.random.randint(0, 2, n_samples)
    })


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_config(temp_dir) -> dict:
    """Create mock configuration for testing."""
    return {
        'data': {
            'languages': ['en', 'pt'],
            'min_chars': 50,
            'rss_feeds': [],
            'price': {
                'symbols': ['PETR4.SA', 'VALE3.SA'],
                'interval': '1d',
                'period': '6mo'
            }
        },
        'sentiment': {
            'model_id': 'ProsusAI/finbert',
            'batch_size': 8,
            'device': 'cpu'
        },
        'aggregation': {
            'window': 'W-MON',
            'decay_half_life': 6
        },
        'model': {
            'type': 'logreg',
            'horizon_bars': 1,
            'calibration': 'isotonic'
        },
        'signals': {
            'threshold_long': 0.6,
            'threshold_short': 0.4,
            'costs_bps': 10
        }
    }
