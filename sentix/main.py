import logging
import yaml
import pandas as pd
import numpy as np
from ingest.rss_client import fetch_rss
from ingest.normalize import load_ticker_map, map_entities
from features.aggregate import build_sentiment_bars
from backtest.label import make_labels
from models.prob_model import ProbModel
from backtest.backtester import run

# Set seeds for determinism
np.random.seed(42)
pd.np.random.seed(42) if hasattr(pd, 'np') else None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Load configs
    with open('config.yml', 'r') as f:
        config = yaml.safe_load(f)
    ticker_map = load_ticker_map('tickers.yml')

    logger.info("Starting Sentix-FinBERT pipeline")

    # 1) Ingest RSS
    logger.info("Ingesting RSS feeds")
    df = fetch_rss(
        feeds=config['data']['rss_feeds'],
        min_chars=config['data']['min_chars'],
        allowed_langs=config['data']['languages']
    )
    if df.empty:
        logger.error("No articles ingested")
        return
    logger.info(f"Ingested {len(df)} articles")

    # 2) Normalize & map
    logger.info("Normalizing and mapping entities")
    df = map_entities(df, ticker_map)
    if df.empty:
        logger.error("No articles after mapping")
        return
    df.to_csv('data/articles_raw.csv', index=False)
    logger.info(f"Mapped to {len(df)} article-ticker pairs")

    # 3) Aggregate
    logger.info("Aggregating sentiment bars")
    bars_df = build_sentiment_bars(
        articles_csv='data/articles_raw.csv',
        window=config['aggregation']['window'],
        config_path='config.yml'
    )
    if bars_df.empty:
        logger.error("No sentiment bars")
        return
    logger.info(f"Aggregated {len(bars_df)} bars")

    # 4) Label
    logger.info("Labeling with prices")
    training_df = make_labels(
        sent_bars_csv='data/sentiment_bars.csv',
        horizon_bars=config['model']['horizon_bars'],
        price_cfg=config['data']['price']
    )
    if training_df.empty:
        logger.error("No training data")
        return
    logger.info(f"Training set has {len(training_df)} rows")

    # 5) Train model
    logger.info("Training model")
    ProbModel.train_and_save('data/training_set.csv', 'outputs/prob_model.pkl')

    # 6) Backtest
    logger.info("Running backtest")
    metrics = run(
        df=training_df,
        model_path='outputs/prob_model.pkl',
        threshold_long=config['signals']['threshold_long'],
        costs_bps=config['signals']['costs_bps']
    )

    # 7) Summary
    logger.info("Pipeline completed")
    logger.info(f"Rows: {len(df)}")
    logger.info(f"Training size: {len(training_df)}")
    logger.info(f"Brier: {metrics['brier']:.4f}")
    logger.info(f"AUC: {metrics['auc']:.4f}")
    logger.info(f"Sharpe: {metrics['sharpe']:.4f}")
    logger.info(f"Total Return: {metrics['total_return']:.4f}")

if __name__ == "__main__":
    main()