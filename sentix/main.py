"""
Sentix - Main Pipeline Orchestrator

End-to-end runner for the sentiment analysis pipeline, from RSS ingestion
through model training and backtesting.
"""

import yaml
import pandas as pd
import numpy as np
from pathlib import Path

from logging_config import setup_logging, get_logger
from ingest.rss_client import fetch_rss
from ingest.normalize import load_ticker_map, map_entities
from features.aggregate import build_sentiment_bars
from backtest.label import make_labels
from models.prob_model import ProbModel
from backtest.backtester import run

# Set seeds for determinism
np.random.seed(42)

# Initialize logging
setup_logging()
logger = get_logger(__name__)


def main() -> None:
    """
    Run the complete Sentix pipeline.
    
    Pipeline steps:
    1. Ingest RSS feeds
    2. Normalize and map entities to tickers
    3. Aggregate sentiment bars
    4. Create labels from price data
    5. Train probability model
    6. Run backtest and generate reports
    """
    # Ensure directories exist
    Path('data').mkdir(exist_ok=True)
    Path('outputs').mkdir(exist_ok=True)
    
    # Load configs
    logger.info("Loading configuration files")
    with open('config.yml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    ticker_map = load_ticker_map('tickers.yml')

    logger.info("=" * 60)
    logger.info("Starting Sentix-FinBERT Pipeline")
    logger.info("=" * 60)

    # 1) Ingest RSS
    logger.info("Step 1/6: Ingesting RSS feeds")
    df = fetch_rss(
        feeds=config['data']['rss_feeds'],
        min_chars=config['data']['min_chars'],
        allowed_langs=config['data']['languages']
    )
    if df.empty:
        logger.error("No articles ingested. Check RSS feeds and filters.")
        return
    logger.info(f"✓ Ingested {len(df)} articles")

    # 2) Normalize & map
    logger.info("Step 2/6: Normalizing and mapping entities")
    df = map_entities(df, ticker_map)
    if df.empty:
        logger.error("No articles matched any tickers. Check tickers.yml aliases.")
        return
    df.to_csv('data/articles_raw.csv', index=False)
    logger.info(f"✓ Mapped to {len(df)} article-ticker pairs")

    # 3) Aggregate
    logger.info("Step 3/6: Aggregating sentiment bars")
    bars_df = build_sentiment_bars(
        articles_csv='data/articles_raw.csv',
        window=config['aggregation']['window'],
        config_path='config.yml'
    )
    if bars_df.empty:
        logger.error("No sentiment bars generated.")
        return
    logger.info(f"✓ Aggregated {len(bars_df)} bars")

    # 4) Label
    logger.info("Step 4/6: Labeling with prices")
    training_df = make_labels(
        sent_bars_csv='data/sentiment_bars.csv',
        horizon_bars=config['model']['horizon_bars'],
        price_cfg=config['data']['price']
    )
    if training_df.empty:
        logger.error("No training data generated. Check price data availability.")
        return
    logger.info(f"✓ Training set has {len(training_df)} rows")

    # 5) Train model
    logger.info("Step 5/6: Training probability model")
    ProbModel.train_and_save('data/training_set.csv', 'outputs/prob_model.pkl')
    logger.info("✓ Model saved to outputs/prob_model.pkl")

    # 6) Backtest
    logger.info("Step 6/6: Running backtest")
    metrics = run(
        df=training_df,
        model_path='outputs/prob_model.pkl',
        threshold_long=config['signals']['threshold_long'],
        costs_bps=config['signals']['costs_bps']
    )

    # Summary
    logger.info("=" * 60)
    logger.info("Pipeline Completed Successfully!")
    logger.info("=" * 60)
    logger.info(f"Articles processed: {len(df)}")
    logger.info(f"Training samples: {len(training_df)}")
    logger.info("-" * 40)
    logger.info("Performance Metrics:")
    logger.info(f"  • Brier Score: {metrics['brier']:.4f}")
    logger.info(f"  • AUC-ROC:     {metrics['auc']:.4f}")
    logger.info(f"  • Sharpe:      {metrics['sharpe']:.2f}")
    logger.info(f"  • Total Return:{metrics['total_return']:.2%}")
    logger.info(f"  • Max DD:      {metrics['max_dd']:.2%}")
    logger.info("-" * 40)
    logger.info("Outputs saved:")
    logger.info("  • outputs/prob_model.pkl")
    logger.info("  • outputs/equity.png")
    logger.info("  • outputs/report.md")


if __name__ == "__main__":
    main()