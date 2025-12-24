"""
Backtester - Event-driven backtesting for sentiment-based strategies.

This module provides backtesting functionality for evaluating the performance
of sentiment-based trading strategies with comprehensive metrics.
"""

from typing import Dict, Any, List
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, brier_score_loss
import matplotlib.pyplot as plt
import re
import logging

from models.prob_model import ProbModel

logger = logging.getLogger(__name__)

# Type aliases
BacktestMetrics = Dict[str, float]

# Feature selection pattern
FEATURE_PATTERN = re.compile(r'(mean|std|min|max|count|unc|decay)')


def run(
    df: pd.DataFrame,
    model_path: str,
    threshold_long: float,
    costs_bps: int
) -> BacktestMetrics:
    """
    Run event-driven backtest on sentiment data.
    
    This function:
    1. Loads the trained probability model
    2. Generates probability predictions for each bar
    3. Simulates a long-only strategy based on probability threshold
    4. Computes comprehensive performance metrics
    5. Saves equity curve and report
    
    Args:
        df: DataFrame with features and labels.
            Must have columns matching FEATURE_PATTERN, 'r_fwd', 'y', 
            'ticker', 'bucket_start'.
        model_path: Path to trained ProbModel pickle file.
        threshold_long: Probability threshold for entering long positions.
        costs_bps: Transaction costs in basis points.
        
    Returns:
        Dictionary with metrics:
            - total_return: Cumulative return
            - win_rate: Fraction of profitable trades
            - profit_factor: Gross profits / gross losses
            - sharpe: Annualized Sharpe ratio
            - max_dd: Maximum drawdown
            - auc: ROC AUC score
            - brier: Brier score (lower is better)
            
    Example:
        >>> metrics = run(
        ...     df=training_df,
        ...     model_path='outputs/prob_model.pkl',
        ...     threshold_long=0.62,
        ...     costs_bps=10
        ... )
        >>> print(f"Sharpe: {metrics['sharpe']:.2f}")
    """
    # Load model
    logger.info(f"Loading model from {model_path}")
    model = ProbModel.load(model_path)

    # Select features
    feature_cols = [col for col in df.columns if FEATURE_PATTERN.match(col)]
    X = df[feature_cols]
    
    logger.info(f"Running backtest with {len(df)} samples and {len(feature_cols)} features")

    # Predict probabilities
    P = model.predict_proba(X)

    # Sort by ticker and time
    df = df.sort_values(['ticker', 'bucket_start']).copy()
    df['P'] = P

    # Compute PnL
    df = _compute_pnl(df, threshold_long, costs_bps)

    # Compute equity curve
    df['equity'] = (1 + df['pnl']).cumprod()

    # Calculate all metrics
    metrics = _compute_metrics(df, P)

    # Save outputs
    _save_equity_plot(df)
    _save_report(metrics)

    logger.info(f"Backtest complete. Sharpe: {metrics['sharpe']:.4f}, AUC: {metrics['auc']:.4f}")
    
    return metrics


def _compute_pnl(
    df: pd.DataFrame,
    threshold_long: float,
    costs_bps: int
) -> pd.DataFrame:
    """
    Compute PnL for each bar based on strategy signals.
    
    Args:
        df: DataFrame with probability predictions and forward returns.
        threshold_long: Threshold for long entry.
        costs_bps: Transaction costs in basis points.
        
    Returns:
        DataFrame with 'pnl' column added.
    """
    df = df.copy()
    df['pnl'] = 0.0
    
    # Long when probability exceeds threshold
    mask = df['P'] > threshold_long
    costs = costs_bps * 1e-4
    df.loc[mask, 'pnl'] = df.loc[mask, 'r_fwd'] - costs
    
    return df


def _compute_metrics(df: pd.DataFrame, P: np.ndarray) -> BacktestMetrics:
    """
    Compute comprehensive backtest metrics.
    
    Args:
        df: DataFrame with PnL and equity.
        P: Probability predictions.
        
    Returns:
        Dictionary of performance metrics.
    """
    y_true = df['y'].values
    pnl_series = df['pnl']
    
    # Classification metrics
    auc = roc_auc_score(y_true, P)
    brier = brier_score_loss(y_true, P)
    
    # Trading metrics
    win_rate = (pnl_series > 0).mean()
    positive_pnl = pnl_series[pnl_series > 0].sum()
    negative_pnl = pnl_series[pnl_series < 0].sum()
    profit_factor = abs(positive_pnl / negative_pnl) if negative_pnl != 0 else np.inf
    
    # Total return
    total_return = df['equity'].iloc[-1] - 1

    # Sharpe ratio (daily resample, annualized)
    sharpe = _compute_sharpe(df)

    # Maximum drawdown
    max_dd = _compute_max_drawdown(df)

    return {
        'total_return': float(total_return),
        'win_rate': float(win_rate),
        'profit_factor': float(profit_factor),
        'sharpe': float(sharpe),
        'max_dd': float(max_dd),
        'auc': float(auc),
        'brier': float(brier)
    }


def _compute_sharpe(df: pd.DataFrame, annualization_factor: int = 252) -> float:
    """
    Compute annualized Sharpe ratio from equity curve.
    
    Args:
        df: DataFrame with 'bucket_start' and 'equity' columns.
        annualization_factor: Number of trading days per year.
        
    Returns:
        Annualized Sharpe ratio.
    """
    try:
        daily_equity = df.set_index('bucket_start')['equity'].resample('D').last().dropna()
        daily_returns = daily_equity.pct_change().dropna()
        
        if len(daily_returns) < 2:
            return 0.0
            
        mean_return = daily_returns.mean()
        std_return = daily_returns.std()
        
        if std_return == 0:
            return 0.0
            
        return float((mean_return / std_return) * np.sqrt(annualization_factor))
        
    except Exception as e:
        logger.warning(f"Error computing Sharpe: {e}")
        return 0.0


def _compute_max_drawdown(df: pd.DataFrame) -> float:
    """
    Compute maximum drawdown from equity curve.
    
    Args:
        df: DataFrame with 'equity' column.
        
    Returns:
        Maximum drawdown as a negative percentage.
    """
    peak = df['equity'].expanding().max()
    drawdown = (df['equity'] - peak) / peak
    return float(drawdown.min())


def _save_equity_plot(df: pd.DataFrame, output_path: str = 'outputs/equity.png') -> None:
    """
    Save equity curve plot to file.
    
    Args:
        df: DataFrame with 'bucket_start' and 'equity' columns.
        output_path: Path to save the plot.
    """
    try:
        plt.figure(figsize=(12, 6))
        plt.plot(df['bucket_start'], df['equity'], linewidth=2, color='#2E86AB')
        plt.fill_between(df['bucket_start'], 1, df['equity'], alpha=0.3, color='#2E86AB')
        plt.axhline(y=1, color='gray', linestyle='--', alpha=0.7)
        plt.title('Equity Curve - Sentiment Strategy', fontsize=14, fontweight='bold')
        plt.xlabel('Time')
        plt.ylabel('Equity (starting at 1.0)')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()
        logger.info(f"Saved equity plot to {output_path}")
    except Exception as e:
        logger.error(f"Error saving equity plot: {e}")


def _save_report(metrics: BacktestMetrics, output_path: str = 'outputs/report.md') -> None:
    """
    Save backtest report to markdown file.
    
    Args:
        metrics: Dictionary of performance metrics.
        output_path: Path to save the report.
    """
    report = f"""# Backtest Report

## Performance Metrics

| Metric | Value |
|--------|-------|
| Total Return | {metrics['total_return']:.2%} |
| Win Rate | {metrics['win_rate']:.2%} |
| Profit Factor | {metrics['profit_factor']:.2f} |
| Sharpe Ratio | {metrics['sharpe']:.2f} |
| Max Drawdown | {metrics['max_dd']:.2%} |

## Model Quality

| Metric | Value |
|--------|-------|
| AUC-ROC | {metrics['auc']:.4f} |
| Brier Score | {metrics['brier']:.4f} |

---
*Report generated automatically by Sentix backtester.*
"""
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"Saved report to {output_path}")
    except Exception as e:
        logger.error(f"Error saving report: {e}")