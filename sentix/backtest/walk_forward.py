"""
Walk-Forward Backtesting - Out-of-sample validation for Sentix.

This module implements walk-forward analysis for proper model evaluation,
simulating real-world trading conditions where the model is trained on
past data and tested on future data.
"""

from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, brier_score_loss, accuracy_score
import matplotlib.pyplot as plt
from datetime import datetime
import re
import logging

from models.prob_model import ProbModel

logger = logging.getLogger(__name__)

# Feature pattern
FEATURE_PATTERN = re.compile(r'(mean|std|min|max|count|unc|decay)')


class WalkForwardBacktester:
    """
    Walk-forward backtesting for out-of-sample evaluation.
    
    Implements expanding or rolling window training with forward testing,
    which better simulates real trading conditions.
    
    Example:
        >>> backtester = WalkForwardBacktester(train_size=0.6, step_size=0.1)
        >>> results = backtester.run(df, threshold=0.62)
        >>> print(results['summary'])
    """
    
    def __init__(
        self,
        train_size: float = 0.6,
        step_size: float = 0.1,
        expanding: bool = True,
        min_train_samples: int = 30
    ):
        """
        Initialize the walk-forward backtester.
        
        Args:
            train_size: Initial training set size as fraction.
            step_size: Step size for each walk-forward iteration.
            expanding: If True, uses expanding window. If False, rolling.
            min_train_samples: Minimum samples required for training.
        """
        self.train_size = train_size
        self.step_size = step_size
        self.expanding = expanding
        self.min_train_samples = min_train_samples
        
        self.results: List[Dict[str, Any]] = []
        self.all_predictions: pd.DataFrame = pd.DataFrame()
    
    def run(
        self,
        df: pd.DataFrame,
        threshold_long: float = 0.62,
        threshold_short: float = 0.38,
        costs_bps: int = 10
    ) -> Dict[str, Any]:
        """
        Run walk-forward backtest.
        
        Args:
            df: DataFrame with features, 'y' label, and 'bucket_start'.
            threshold_long: Probability threshold for long positions.
            threshold_short: Probability threshold for short positions.
            costs_bps: Transaction costs in basis points.
            
        Returns:
            Dictionary with backtest results and metrics.
        """
        # Sort by time
        df = df.sort_values('bucket_start').reset_index(drop=True)
        
        # Get feature columns
        feature_cols = [col for col in df.columns if FEATURE_PATTERN.match(col)]
        
        n = len(df)
        initial_train_end = int(n * self.train_size)
        step = int(n * self.step_size)
        
        if initial_train_end < self.min_train_samples:
            logger.error("Not enough data for walk-forward testing")
            return {'error': 'Insufficient data'}
        
        self.results = []
        all_test_indices = []
        all_predictions = []
        
        # Walk-forward iterations
        train_start = 0
        train_end = initial_train_end
        iteration = 0
        
        while train_end < n - 1:
            test_end = min(train_end + step, n)
            
            if test_end <= train_end:
                break
            
            # Train/test split
            if self.expanding:
                train_df = df.iloc[train_start:train_end]
            else:
                # Rolling window
                window_size = int(n * self.train_size)
                train_df = df.iloc[max(0, train_end - window_size):train_end]
            
            test_df = df.iloc[train_end:test_end]
            
            logger.info(f"Iteration {iteration}: Train [{train_start if self.expanding else max(0, train_end - int(n * self.train_size))}:{train_end}], Test [{train_end}:{test_end}]")
            
            # Train model
            X_train = train_df[feature_cols]
            y_train = train_df['y']
            
            model = ProbModel()
            model.fit(X_train, y_train)
            
            # Predict on test
            X_test = test_df[feature_cols]
            y_test = test_df['y']
            
            probabilities = model.predict_proba(X_test)
            
            # Calculate metrics for this fold
            fold_metrics = self._calculate_fold_metrics(
                y_test.values, probabilities, threshold_long, threshold_short, costs_bps,
                test_df.get('r_fwd', pd.Series([0] * len(test_df)))
            )
            fold_metrics['iteration'] = iteration
            fold_metrics['train_size'] = len(train_df)
            fold_metrics['test_size'] = len(test_df)
            
            self.results.append(fold_metrics)
            
            # Store predictions
            all_test_indices.extend(test_df.index.tolist())
            all_predictions.extend(probabilities.tolist())
            
            # Move window
            train_end = test_end
            iteration += 1
        
        # Combine all predictions
        self.all_predictions = pd.DataFrame({
            'index': all_test_indices,
            'probability': all_predictions
        })
        
        # Calculate aggregate metrics
        summary = self._calculate_summary_metrics(df, feature_cols, all_test_indices, all_predictions)
        
        return {
            'summary': summary,
            'fold_results': self.results,
            'predictions': self.all_predictions,
            'n_folds': len(self.results)
        }
    
    def _calculate_fold_metrics(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        threshold_long: float,
        threshold_short: float,
        costs_bps: int,
        r_fwd: pd.Series
    ) -> Dict[str, float]:
        """Calculate metrics for a single fold."""
        metrics = {}
        
        # Classification metrics
        if len(np.unique(y_true)) > 1:
            metrics['auc'] = roc_auc_score(y_true, y_prob)
        else:
            metrics['auc'] = 0.5
        
        metrics['brier'] = brier_score_loss(y_true, y_prob)
        
        # Accuracy at threshold
        y_pred = (y_prob > 0.5).astype(int)
        metrics['accuracy'] = accuracy_score(y_true, y_pred)
        
        # Trading metrics
        costs = costs_bps * 1e-4
        pnl = np.where(y_prob > threshold_long, r_fwd.values - costs, 0)
        
        if len(pnl) > 0:
            metrics['total_return'] = (1 + pnl).prod() - 1
            metrics['win_rate'] = (pnl > 0).mean()
            metrics['n_trades'] = (y_prob > threshold_long).sum()
        else:
            metrics['total_return'] = 0
            metrics['win_rate'] = 0
            metrics['n_trades'] = 0
        
        return metrics
    
    def _calculate_summary_metrics(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        test_indices: List[int],
        predictions: List[float]
    ) -> Dict[str, Any]:
        """Calculate summary metrics across all folds."""
        if not self.results:
            return {}
        
        # Aggregate fold metrics
        avg_auc = np.mean([r['auc'] for r in self.results])
        avg_brier = np.mean([r['brier'] for r in self.results])
        avg_accuracy = np.mean([r['accuracy'] for r in self.results])
        total_return = np.prod([1 + r['total_return'] for r in self.results]) - 1
        
        # Calculate on all predictions
        if test_indices:
            all_y_true = df.loc[test_indices, 'y'].values
            all_y_prob = np.array(predictions)
            
            if len(np.unique(all_y_true)) > 1:
                overall_auc = roc_auc_score(all_y_true, all_y_prob)
            else:
                overall_auc = 0.5
            overall_brier = brier_score_loss(all_y_true, all_y_prob)
        else:
            overall_auc = avg_auc
            overall_brier = avg_brier
        
        return {
            'n_folds': len(self.results),
            'avg_auc': round(avg_auc, 4),
            'avg_brier': round(avg_brier, 4),
            'avg_accuracy': round(avg_accuracy, 4),
            'overall_auc': round(overall_auc, 4),
            'overall_brier': round(overall_brier, 4),
            'total_return': round(total_return, 4),
            'total_samples': sum(r['test_size'] for r in self.results)
        }
    
    def plot_fold_metrics(self, output_path: Optional[str] = None) -> None:
        """
        Plot metrics across folds.
        
        Args:
            output_path: Path to save the plot.
        """
        if not self.results:
            logger.warning("No results to plot")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        
        iterations = [r['iteration'] for r in self.results]
        
        # AUC
        axes[0, 0].plot(iterations, [r['auc'] for r in self.results], 'b-o')
        axes[0, 0].axhline(y=0.5, color='gray', linestyle='--', alpha=0.7)
        axes[0, 0].set_title('AUC por Fold')
        axes[0, 0].set_xlabel('Iteração')
        axes[0, 0].set_ylabel('AUC')
        
        # Brier Score
        axes[0, 1].plot(iterations, [r['brier'] for r in self.results], 'r-o')
        axes[0, 1].axhline(y=0.25, color='gray', linestyle='--', alpha=0.7)
        axes[0, 1].set_title('Brier Score por Fold')
        axes[0, 1].set_xlabel('Iteração')
        axes[0, 1].set_ylabel('Brier')
        
        # Return
        axes[1, 0].bar(iterations, [r['total_return'] * 100 for r in self.results], 
                       color=['green' if r['total_return'] > 0 else 'red' for r in self.results])
        axes[1, 0].axhline(y=0, color='gray', linestyle='-', alpha=0.7)
        axes[1, 0].set_title('Retorno por Fold')
        axes[1, 0].set_xlabel('Iteração')
        axes[1, 0].set_ylabel('Retorno (%)')
        
        # Cumulative Return
        cumulative = np.cumprod([1 + r['total_return'] for r in self.results])
        axes[1, 1].plot(iterations, cumulative, 'g-o')
        axes[1, 1].axhline(y=1, color='gray', linestyle='--', alpha=0.7)
        axes[1, 1].fill_between(iterations, 1, cumulative, alpha=0.3, color='green')
        axes[1, 1].set_title('Retorno Cumulativo')
        axes[1, 1].set_xlabel('Iteração')
        axes[1, 1].set_ylabel('Equity')
        
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            logger.info(f"Walk-forward plot saved to {output_path}")
            plt.close()
        else:
            plt.show()


def run_walk_forward(
    data_path: str = 'data/training_set.csv',
    threshold: float = 0.62,
    costs_bps: int = 10,
    output_dir: str = 'outputs'
) -> Dict[str, Any]:
    """
    Convenience function to run walk-forward backtest.
    
    Args:
        data_path: Path to training data CSV.
        threshold: Long threshold.
        costs_bps: Transaction costs.
        output_dir: Output directory.
        
    Returns:
        Backtest results.
    """
    from pathlib import Path
    
    df = pd.read_csv(data_path)
    df['bucket_start'] = pd.to_datetime(df['bucket_start'])
    
    backtester = WalkForwardBacktester(
        train_size=0.6,
        step_size=0.1,
        expanding=True
    )
    
    results = backtester.run(df, threshold_long=threshold, costs_bps=costs_bps)
    
    # Save plot
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    backtester.plot_fold_metrics(str(output_path / 'walk_forward_metrics.png'))
    
    # Log summary
    if 'summary' in results:
        logger.info("Walk-Forward Backtest Summary:")
        for key, value in results['summary'].items():
            logger.info(f"  {key}: {value}")
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    try:
        results = run_walk_forward()
        
        print("\n=== Walk-Forward Summary ===")
        for key, value in results.get('summary', {}).items():
            print(f"{key}: {value}")
            
    except FileNotFoundError as e:
        print(f"Required files not found: {e}")
