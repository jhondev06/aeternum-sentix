import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, brier_score_loss
import matplotlib.pyplot as plt
from models.prob_model import ProbModel
import re

def run(df: pd.DataFrame, model_path: str, threshold_long: float, costs_bps: int) -> dict:
    # Load model
    model = ProbModel.load(model_path)

    # Select features
    feature_cols = [col for col in df.columns if re.match(r'(mean|std|min|max|count|unc|decay)', col)]
    X = df[feature_cols]

    # Predict probabilities
    P = model.predict_proba(X)

    # Sort
    df = df.sort_values(['ticker', 'bucket_start']).copy()
    df['P'] = P

    # Compute PnL
    df['pnl'] = 0.0
    mask = df['P'] > threshold_long
    df.loc[mask, 'pnl'] = df.loc[mask, 'r_fwd'] - costs_bps * 1e-4

    # Equity curve
    df['equity'] = (1 + df['pnl']).cumprod()

    # Metrics
    y_true = df['y']
    auc = roc_auc_score(y_true, P)
    brier = brier_score_loss(y_true, P)

    pnl_series = df['pnl']
    win_rate = (pnl_series > 0).mean()
    positive_pnl = pnl_series[pnl_series > 0].sum()
    negative_pnl = pnl_series[pnl_series < 0].sum()
    profit_factor = abs(positive_pnl / negative_pnl) if negative_pnl != 0 else np.inf

    total_return = df['equity'].iloc[-1] - 1

    # Sharpe (daily resample)
    daily_equity = df.set_index('bucket_start')['equity'].resample('D').last().dropna()
    daily_returns = daily_equity.pct_change().dropna()
    sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if len(daily_returns) > 0 else 0

    # Max Drawdown
    peak = df['equity'].expanding().max()
    drawdown = (df['equity'] - peak) / peak
    max_dd = drawdown.min()

    # Save equity plot
    plt.figure(figsize=(10, 6))
    plt.plot(df['bucket_start'], df['equity'])
    plt.title('Equity Curve')
    plt.xlabel('Time')
    plt.ylabel('Equity')
    plt.savefig('outputs/equity.png')
    plt.close()

    # Save report
    report = f"""
# Backtest Report

- Total Return: {total_return:.4f}
- Win Rate: {win_rate:.4f}
- Profit Factor: {profit_factor:.4f}
- Sharpe Ratio: {sharpe:.4f}
- Max Drawdown: {max_dd:.4f}
- AUC: {auc:.4f}
- Brier Score: {brier:.4f}
"""
    with open('outputs/report.md', 'w') as f:
        f.write(report)

    return {
        'total_return': total_return,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'sharpe': sharpe,
        'max_dd': max_dd,
        'auc': auc,
        'brier': brier
    }