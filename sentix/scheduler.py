"""
Scheduler - Automated task scheduling for Sentix.

This module provides background job scheduling for:
- RSS feed ingestion
- Price data updates
- Alert processing
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from typing import Optional, Callable, Dict, Any
import logging
import yaml
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SentixScheduler:
    """
    Background task scheduler for Sentix.
    
    Manages periodic jobs for data ingestion, processing, and alerts.
    
    Example:
        >>> scheduler = SentixScheduler()
        >>> scheduler.start()
        >>> # Jobs run in background
        >>> scheduler.stop()
    """
    
    def __init__(self, config_path: str = "config.yml"):
        """
        Initialize the scheduler.
        
        Args:
            config_path: Path to configuration file.
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.scheduler = BackgroundScheduler()
        self._setup_jobs()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}")
            return {}
    
    def _setup_jobs(self) -> None:
        """Configure scheduled jobs."""
        
        # RSS Ingestion - Every 2 hours
        self.scheduler.add_job(
            self._job_ingest_rss,
            IntervalTrigger(hours=2),
            id='ingest_rss',
            name='RSS Feed Ingestion',
            replace_existing=True
        )
        
        # Price Update - Every hour during market hours
        self.scheduler.add_job(
            self._job_update_prices,
            CronTrigger(hour='10-18', minute=0),  # 10am-6pm
            id='update_prices',
            name='Price Data Update',
            replace_existing=True
        )
        
        # Alert Processing - Every 30 minutes
        self.scheduler.add_job(
            self._job_process_alerts,
            IntervalTrigger(minutes=30),
            id='process_alerts',
            name='Alert Processing',
            replace_existing=True
        )
        
        # Sentiment Aggregation - Every 4 hours
        self.scheduler.add_job(
            self._job_aggregate_sentiment,
            IntervalTrigger(hours=4),
            id='aggregate_sentiment',
            name='Sentiment Aggregation',
            replace_existing=True
        )
        
        logger.info("Scheduler jobs configured")
    
    def start(self) -> None:
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")
    
    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("Scheduler stopped")
    
    def run_job_now(self, job_id: str) -> None:
        """
        Execute a job immediately.
        
        Args:
            job_id: ID of the job to run.
        """
        job = self.scheduler.get_job(job_id)
        if job:
            job.func()
            logger.info(f"Job {job_id} executed manually")
        else:
            logger.warning(f"Job not found: {job_id}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get scheduler status and job information.
        
        Returns:
            Dictionary with scheduler status.
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': str(job.next_run_time) if job.next_run_time else None
            })
        
        return {
            'running': self.scheduler.running,
            'jobs': jobs,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    # =========================================================================
    # Job Functions
    # =========================================================================
    
    def _job_ingest_rss(self) -> None:
        """Job: Ingest articles from RSS feeds."""
        logger.info("Running scheduled RSS ingestion")
        
        try:
            from ingest.rss_client import fetch_rss
            from ingest.normalize import load_ticker_map, map_entities
            from database import save_articles
            
            # Fetch articles
            df = fetch_rss(
                feeds=self.config.get('data', {}).get('rss_feeds', []),
                min_chars=self.config.get('data', {}).get('min_chars', 120),
                allowed_langs=self.config.get('data', {}).get('languages', ['pt'])
            )
            
            if df.empty:
                logger.info("No new articles from RSS feeds")
                return
            
            # Map to tickers
            ticker_map = load_ticker_map('tickers.yml')
            df = map_entities(df, ticker_map)
            
            if not df.empty:
                # Save to database
                count = save_articles(df)
                logger.info(f"Ingested and saved {count} articles")
                
                # Also save CSV for compatibility
                df.to_csv('data/articles_raw.csv', index=False)
            
        except Exception as e:
            logger.error(f"RSS ingestion job failed: {e}")
    
    def _job_update_prices(self) -> None:
        """Job: Update price data from yfinance."""
        logger.info("Running scheduled price update")
        
        try:
            import yfinance as yf
            from database import save_prices
            import pandas as pd
            
            symbols = self.config.get('data', {}).get('price', {}).get('symbols', [])
            
            for symbol in symbols:
                if symbol in ['IPCA', 'PIB', 'SELIC']:
                    continue  # Skip non-tradeable
                
                try:
                    data = yf.download(symbol, period='5d', interval='1h', progress=False)
                    if not data.empty:
                        data = data.reset_index()
                        if isinstance(data.columns, pd.MultiIndex):
                            data.columns = data.columns.droplevel(1)
                        
                        # Rename columns
                        date_col = 'Datetime' if 'Datetime' in data.columns else 'Date'
                        data = data.rename(columns={
                            date_col: 'timestamp',
                            'Open': 'open',
                            'High': 'high',
                            'Low': 'low',
                            'Close': 'close',
                            'Volume': 'volume'
                        })
                        data['ticker'] = symbol
                        
                        save_prices(data)
                        logger.info(f"Updated prices for {symbol}")
                        
                except Exception as e:
                    logger.warning(f"Failed to update prices for {symbol}: {e}")
            
        except Exception as e:
            logger.error(f"Price update job failed: {e}")
    
    def _job_process_alerts(self) -> None:
        """Job: Process alert rules."""
        logger.info("Running scheduled alert processing")
        
        try:
            from database import load_sentiment_bars, save_alert
            from models.prob_model import ProbModel
            import os
            
            # Load latest sentiment bars
            bars_df = load_sentiment_bars()
            
            if bars_df.empty:
                logger.info("No sentiment data for alert processing")
                return
            
            # Load model if exists
            model_path = 'outputs/prob_model.pkl'
            if not os.path.exists(model_path):
                logger.warning("Model not found for alert processing")
                return
            
            model = ProbModel.load(model_path)
            
            # Get thresholds from config
            threshold_long = self.config.get('signals', {}).get('threshold_long', 0.62)
            threshold_short = self.config.get('signals', {}).get('threshold_short', 0.38)
            
            # Calculate probabilities for latest bars
            for ticker in bars_df['ticker'].unique():
                ticker_data = bars_df[bars_df['ticker'] == ticker].iloc[-1:]
                
                if ticker_data.empty:
                    continue
                
                try:
                    prob = model.predict_proba(ticker_data)[0]
                    
                    # Check thresholds
                    if prob > threshold_long:
                        message = f"🟢 {ticker}: Alta probabilidade de subida ({prob:.1%})"
                        save_alert(
                            rule_id='auto_long',
                            ticker=ticker,
                            probability=prob,
                            action_type='log',
                            action_result='triggered',
                            message=message
                        )
                        logger.info(message)
                        
                        # Send Telegram if enabled
                        self._send_telegram_alert(message)
                        
                    elif prob < threshold_short:
                        message = f"🔴 {ticker}: Alta probabilidade de descida ({prob:.1%})"
                        save_alert(
                            rule_id='auto_short',
                            ticker=ticker,
                            probability=prob,
                            action_type='log',
                            action_result='triggered',
                            message=message
                        )
                        logger.info(message)
                        self._send_telegram_alert(message)
                        
                except Exception as e:
                    logger.warning(f"Error processing alerts for {ticker}: {e}")
            
        except Exception as e:
            logger.error(f"Alert processing job failed: {e}")
    
    def _job_aggregate_sentiment(self) -> None:
        """Job: Re-aggregate sentiment bars."""
        logger.info("Running scheduled sentiment aggregation")
        
        try:
            from features.aggregate import build_sentiment_bars
            from database import save_sentiment_bars
            
            bars_df = build_sentiment_bars(
                articles_csv='data/articles_raw.csv',
                window=self.config.get('aggregation', {}).get('window', 'W-MON'),
                config_path=self.config_path
            )
            
            if not bars_df.empty:
                save_sentiment_bars(bars_df)
                logger.info(f"Aggregated {len(bars_df)} sentiment bars")
            
        except Exception as e:
            logger.error(f"Sentiment aggregation job failed: {e}")
    
    def _send_telegram_alert(self, message: str) -> None:
        """Send alert via Telegram if enabled."""
        telegram_config = self.config.get('telegram', {})
        
        if not telegram_config.get('enabled', False):
            return
        
        try:
            from notify.telegram import send_alert
            send_alert(
                token=telegram_config.get('token', ''),
                chat_id=telegram_config.get('chat_id', ''),
                msg=message
            )
        except Exception as e:
            logger.warning(f"Failed to send Telegram alert: {e}")


# Global scheduler instance
_scheduler: Optional[SentixScheduler] = None


def get_scheduler() -> SentixScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = SentixScheduler()
    return _scheduler


def start_scheduler() -> None:
    """Start the global scheduler."""
    get_scheduler().start()


def stop_scheduler() -> None:
    """Stop the global scheduler."""
    if _scheduler:
        _scheduler.stop()


if __name__ == "__main__":
    # Run scheduler standalone
    import time
    
    scheduler = SentixScheduler()
    scheduler.start()
    
    print("Scheduler running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.stop()
        print("Scheduler stopped.")
