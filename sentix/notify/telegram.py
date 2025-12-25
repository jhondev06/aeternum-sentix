"""
Telegram Notifications - Enhanced Telegram alerting for Sentix.

This module provides rich Telegram notifications with formatting,
emojis, and detailed alert information.
"""

from typing import Optional, List, Dict, Any
import requests
import pandas as pd
import yaml
import os
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Telegram API base URL
TELEGRAM_API = "https://api.telegram.org/bot{token}"


def send_alert(token: str, chat_id: str, msg: str) -> bool:
    """
    Send a simple text alert via Telegram.
    
    Args:
        token: Telegram bot token.
        chat_id: Target chat ID.
        msg: Message text.
        
    Returns:
        True if sent successfully, False otherwise.
    """
    if not token or not chat_id:
        logger.warning("Telegram credentials not configured")
        return False
    
    url = f"{TELEGRAM_API.format(token=token)}/sendMessage"
    
    try:
        response = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML"
            },
            timeout=10
        )
        response.raise_for_status()
        logger.info(f"Telegram alert sent to {chat_id}")
        return True
        
    except requests.RequestException as e:
        logger.error(f"Failed to send Telegram alert: {e}")
        return False


def send_probability_alert(
    token: str,
    chat_id: str,
    ticker: str,
    probability: float,
    direction: str,
    articles: Optional[List[Dict[str, str]]] = None,
    sentiment_score: Optional[float] = None
) -> bool:
    """
    Send a rich probability alert with formatting.
    
    Args:
        token: Telegram bot token.
        chat_id: Target chat ID.
        ticker: Ticker symbol.
        probability: Probability value (0-1).
        direction: Either 'up' or 'down'.
        articles: Optional list of related articles.
        sentiment_score: Optional sentiment score.
        
    Returns:
        True if sent successfully.
    """
    # Choose emoji based on direction
    if direction == 'up':
        emoji = "🟢" if probability > 0.7 else "📈"
        direction_text = "SUBIDA"
        bar = _create_probability_bar(probability, positive=True)
    else:
        emoji = "🔴" if probability < 0.3 else "📉"
        direction_text = "DESCIDA"
        bar = _create_probability_bar(1 - probability, positive=False)
    
    # Format timestamp
    timestamp = datetime.now().strftime("%d/%m %H:%M")
    
    # Build message
    msg = f"""
{emoji} <b>ALERTA SENTIX</b> {emoji}

<b>Ticker:</b> {ticker}
<b>Sinal:</b> Alta probabilidade de {direction_text}
<b>Probabilidade:</b> {probability:.1%}

{bar}
"""
    
    # Add sentiment score if available
    if sentiment_score is not None:
        sent_emoji = "😊" if sentiment_score > 0 else "😟" if sentiment_score < 0 else "😐"
        msg += f"\n<b>Sentimento médio:</b> {sent_emoji} {sentiment_score:+.2f}\n"
    
    # Add articles if available
    if articles and len(articles) > 0:
        msg += "\n<b>📰 Notícias relacionadas:</b>\n"
        for i, article in enumerate(articles[:3], 1):
            title = article.get('title', 'Sem título')[:60]
            url = article.get('url', '#')
            msg += f"{i}. <a href='{url}'>{title}</a>\n"
    
    msg += f"\n<i>⏰ {timestamp}</i>"
    
    return send_alert(token, chat_id, msg)


def send_daily_summary(
    token: str,
    chat_id: str,
    summary: Dict[str, Any]
) -> bool:
    """
    Send a daily summary of sentiment analysis.
    
    Args:
        token: Telegram bot token.
        chat_id: Target chat ID.
        summary: Dictionary with summary data.
        
    Returns:
        True if sent successfully.
    """
    date_str = datetime.now().strftime("%d/%m/%Y")
    
    msg = f"""
📊 <b>RESUMO DIÁRIO SENTIX</b>
<i>{date_str}</i>

<b>📈 Artigos processados:</b> {summary.get('articles_count', 0)}
<b>🎯 Alertas disparados:</b> {summary.get('alerts_count', 0)}

<b>Top Probabilidades de Subida:</b>
"""
    
    # Add top bullish tickers
    top_bullish = summary.get('top_bullish', [])
    for ticker, prob in top_bullish[:5]:
        bar = "🟩" * int(prob * 5) + "⬜" * (5 - int(prob * 5))
        msg += f"  {ticker}: {bar} {prob:.0%}\n"
    
    msg += "\n<b>Top Probabilidades de Descida:</b>\n"
    
    # Add top bearish tickers
    top_bearish = summary.get('top_bearish', [])
    for ticker, prob in top_bearish[:5]:
        bar = "🟥" * int((1-prob) * 5) + "⬜" * (5 - int((1-prob) * 5))
        msg += f"  {ticker}: {bar} {prob:.0%}\n"
    
    msg += "\n<i>💡 Acesse o dashboard para mais detalhes</i>"
    
    return send_alert(token, chat_id, msg)


def _create_probability_bar(prob: float, positive: bool = True) -> str:
    """
    Create a visual probability bar.
    
    Args:
        prob: Probability value (0-1).
        positive: True for green, False for red.
        
    Returns:
        String representation of probability bar.
    """
    filled = int(prob * 10)
    empty = 10 - filled
    
    if positive:
        bar = "🟩" * filled + "⬜" * empty
    else:
        bar = "🟥" * filled + "⬜" * empty
    
    return f"[{bar}] {prob:.0%}"


def load_config(config_path: str = 'config.yml') -> Dict[str, Any]:
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}


def run_threshold_check(config_path: str = 'config.yml') -> None:
    """
    Check latest sentiment bars and send alerts for threshold crossings.
    
    This is the main entry point for scheduled alert checking.
    """
    config = load_config(config_path)
    
    telegram_config = config.get('telegram', {})
    if not telegram_config.get('enabled', False):
        logger.info("Telegram notifications disabled")
        return
    
    token = telegram_config.get('token', '')
    chat_id = telegram_config.get('chat_id', '')
    threshold_long = config.get('signals', {}).get('threshold_long', 0.62)
    threshold_short = config.get('signals', {}).get('threshold_short', 0.38)
    
    # Check required files
    required_files = ['outputs/prob_model.pkl', 'data/sentiment_bars.csv']
    for f in required_files:
        if not os.path.exists(f):
            logger.warning(f"Required file not found: {f}")
            return
    
    # Load model and data
    from models.prob_model import ProbModel
    model = ProbModel.load('outputs/prob_model.pkl')
    
    bars_df = pd.read_csv('data/sentiment_bars.csv')
    bars_df['bucket_start'] = pd.to_datetime(bars_df['bucket_start'])
    
    # Load articles for context
    articles_df = None
    if os.path.exists('data/articles_raw.csv'):
        articles_df = pd.read_csv('data/articles_raw.csv')
        articles_df['published_at'] = pd.to_datetime(articles_df['published_at'])
    
    # Check each ticker
    feature_pattern = re.compile(r'(mean|std|min|max|count|unc|decay)')
    alerts_sent = 0
    
    for ticker in bars_df['ticker'].unique():
        ticker_bars = bars_df[bars_df['ticker'] == ticker].sort_values('bucket_start')
        
        if ticker_bars.empty:
            continue
        
        last_bar = ticker_bars.iloc[-1]
        features = last_bar.to_frame().T
        feature_cols = [col for col in features.columns if feature_pattern.match(col)]
        
        try:
            prob = model.predict_proba(features[feature_cols])[0]
        except Exception as e:
            logger.warning(f"Error predicting for {ticker}: {e}")
            continue
        
        # Get related articles
        articles = []
        if articles_df is not None:
            related = articles_df[articles_df['ticker'] == ticker].nlargest(3, 'published_at')
            articles = related[['title', 'url']].to_dict('records')
        
        # Check thresholds
        if prob > threshold_long:
            send_probability_alert(
                token=token,
                chat_id=chat_id,
                ticker=ticker,
                probability=prob,
                direction='up',
                articles=articles,
                sentiment_score=last_bar.get('mean_sent')
            )
            alerts_sent += 1
            
        elif prob < threshold_short:
            send_probability_alert(
                token=token,
                chat_id=chat_id,
                ticker=ticker,
                probability=prob,
                direction='down',
                articles=articles,
                sentiment_score=last_bar.get('mean_sent')
            )
            alerts_sent += 1
    
    logger.info(f"Threshold check complete. Alerts sent: {alerts_sent}")


if __name__ == "__main__":
    run_threshold_check()