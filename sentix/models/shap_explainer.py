"""
SHAP Explainer - Model interpretability for Sentix.

This module provides SHAP (SHapley Additive exPlanations) analysis
for the probability model, enabling feature importance visualization
and individual prediction explanations.
"""

from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np
import shap
import matplotlib.pyplot as plt
from pathlib import Path
import logging
import re

logger = logging.getLogger(__name__)

# Feature pattern for selection
FEATURE_PATTERN = re.compile(r'(mean|std|min|max|count|unc|decay)')


class ShapExplainer:
    """
    SHAP-based model explainer for Sentix.
    
    Provides methods for computing SHAP values, generating
    plots, and extracting feature importance.
    
    Example:
        >>> from models.prob_model import ProbModel
        >>> model = ProbModel.load('outputs/prob_model.pkl')
        >>> explainer = ShapExplainer(model)
        >>> importance = explainer.get_feature_importance(X)
    """
    
    def __init__(self, model, background_data: Optional[pd.DataFrame] = None):
        """
        Initialize the SHAP explainer.
        
        Args:
            model: Trained ProbModel instance.
            background_data: Optional background dataset for SHAP.
                           If None, uses KernelExplainer defaults.
        """
        self.model = model
        self.background_data = background_data
        self.explainer = None
        self._shap_values = None
        
    def _create_explainer(self, X: pd.DataFrame) -> None:
        """Create the SHAP explainer based on model type."""
        # For sklearn models, use TreeExplainer if possible, else Kernel
        try:
            # Try to access the base estimator
            base_model = self.model.model.calibrated_classifiers_[0].estimator
            
            # For Logistic Regression, use LinearExplainer
            if hasattr(base_model, 'coef_'):
                # Use a sample for background
                if self.background_data is not None:
                    background = self.background_data.head(100)
                else:
                    background = X.head(100)
                
                self.explainer = shap.LinearExplainer(
                    base_model,
                    background.fillna(0)
                )
            else:
                # Fallback to KernelExplainer
                self._create_kernel_explainer(X)
                
        except Exception as e:
            logger.warning(f"Could not create LinearExplainer: {e}")
            self._create_kernel_explainer(X)
    
    def _create_kernel_explainer(self, X: pd.DataFrame) -> None:
        """Create a KernelExplainer as fallback."""
        if self.background_data is not None:
            background = self.background_data.head(50)
        else:
            background = X.sample(min(50, len(X)), random_state=42)
        
        def predict_fn(x):
            df = pd.DataFrame(x, columns=X.columns)
            return self.model.predict_proba(df)
        
        self.explainer = shap.KernelExplainer(predict_fn, background.fillna(0))
    
    def compute_shap_values(self, X: pd.DataFrame) -> np.ndarray:
        """
        Compute SHAP values for the given data.
        
        Args:
            X: Feature DataFrame.
            
        Returns:
            Array of SHAP values (n_samples x n_features).
        """
        if self.explainer is None:
            self._create_explainer(X)
        
        X_clean = X.fillna(0)
        
        logger.info(f"Computing SHAP values for {len(X)} samples")
        self._shap_values = self.explainer.shap_values(X_clean)
        
        # Handle multi-class output
        if isinstance(self._shap_values, list):
            self._shap_values = self._shap_values[1]  # Positive class
        
        return self._shap_values
    
    def get_feature_importance(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Get global feature importance based on mean |SHAP|.
        
        Args:
            X: Feature DataFrame.
            
        Returns:
            DataFrame with feature importance sorted by importance.
        """
        if self._shap_values is None:
            self.compute_shap_values(X)
        
        importance = pd.DataFrame({
            'feature': X.columns,
            'importance': np.abs(self._shap_values).mean(axis=0)
        })
        
        importance = importance.sort_values('importance', ascending=False)
        importance['importance_pct'] = (
            importance['importance'] / importance['importance'].sum() * 100
        )
        
        return importance.reset_index(drop=True)
    
    def explain_prediction(
        self,
        X: pd.DataFrame,
        idx: int = 0
    ) -> Dict[str, Any]:
        """
        Get detailed explanation for a single prediction.
        
        Args:
            X: Feature DataFrame.
            idx: Index of the sample to explain.
            
        Returns:
            Dictionary with prediction explanation.
        """
        if self._shap_values is None:
            self.compute_shap_values(X)
        
        sample_shap = self._shap_values[idx]
        sample_features = X.iloc[idx]
        
        # Get base value (expected value)
        base_value = self.explainer.expected_value
        if isinstance(base_value, np.ndarray):
            base_value = base_value[1] if len(base_value) > 1 else base_value[0]
        
        # Create explanation dataframe
        explanation_df = pd.DataFrame({
            'feature': X.columns,
            'value': sample_features.values,
            'shap_value': sample_shap,
            'contribution': np.abs(sample_shap)
        }).sort_values('contribution', ascending=False)
        
        return {
            'base_value': float(base_value),
            'prediction': float(base_value + sample_shap.sum()),
            'top_features': explanation_df.head(5).to_dict('records'),
            'all_features': explanation_df.to_dict('records')
        }
    
    def plot_summary(
        self,
        X: pd.DataFrame,
        output_path: Optional[str] = None,
        max_display: int = 10
    ) -> None:
        """
        Generate SHAP summary plot.
        
        Args:
            X: Feature DataFrame.
            output_path: Path to save the plot. If None, displays.
            max_display: Maximum features to display.
        """
        if self._shap_values is None:
            self.compute_shap_values(X)
        
        plt.figure(figsize=(10, 6))
        shap.summary_plot(
            self._shap_values,
            X.fillna(0),
            max_display=max_display,
            show=False
        )
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            logger.info(f"SHAP summary plot saved to {output_path}")
            plt.close()
        else:
            plt.show()
    
    def plot_bar(
        self,
        X: pd.DataFrame,
        output_path: Optional[str] = None,
        max_display: int = 10
    ) -> None:
        """
        Generate SHAP bar plot (feature importance).
        
        Args:
            X: Feature DataFrame.
            output_path: Path to save the plot.
            max_display: Maximum features to display.
        """
        if self._shap_values is None:
            self.compute_shap_values(X)
        
        plt.figure(figsize=(10, 6))
        shap.summary_plot(
            self._shap_values,
            X.fillna(0),
            plot_type='bar',
            max_display=max_display,
            show=False
        )
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            logger.info(f"SHAP bar plot saved to {output_path}")
            plt.close()
        else:
            plt.show()
    
    def plot_waterfall(
        self,
        X: pd.DataFrame,
        idx: int = 0,
        output_path: Optional[str] = None
    ) -> None:
        """
        Generate SHAP waterfall plot for a single prediction.
        
        Args:
            X: Feature DataFrame.
            idx: Index of sample to explain.
            output_path: Path to save the plot.
        """
        if self._shap_values is None:
            self.compute_shap_values(X)
        
        # Get base value
        base_value = self.explainer.expected_value
        if isinstance(base_value, np.ndarray):
            base_value = base_value[1] if len(base_value) > 1 else base_value[0]
        
        # Create Explanation object
        explanation = shap.Explanation(
            values=self._shap_values[idx],
            base_values=base_value,
            data=X.iloc[idx].fillna(0).values,
            feature_names=X.columns.tolist()
        )
        
        plt.figure(figsize=(10, 6))
        shap.waterfall_plot(explanation, show=False)
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            logger.info(f"SHAP waterfall plot saved to {output_path}")
            plt.close()
        else:
            plt.show()


def get_shap_importance(model, X: pd.DataFrame) -> pd.DataFrame:
    """
    Convenience function to get feature importance.
    
    Args:
        model: Trained ProbModel.
        X: Feature DataFrame.
        
    Returns:
        DataFrame with feature importance.
    """
    explainer = ShapExplainer(model)
    return explainer.get_feature_importance(X)


def generate_shap_report(
    model,
    X: pd.DataFrame,
    output_dir: str = 'outputs'
) -> Dict[str, Any]:
    """
    Generate complete SHAP analysis report.
    
    Args:
        model: Trained ProbModel.
        X: Feature DataFrame.
        output_dir: Directory for output files.
        
    Returns:
        Dictionary with analysis results.
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    explainer = ShapExplainer(model)
    
    # Compute values
    explainer.compute_shap_values(X)
    
    # Get importance
    importance = explainer.get_feature_importance(X)
    
    # Generate plots
    explainer.plot_bar(X, output_path=str(output_path / 'shap_importance.png'))
    explainer.plot_summary(X, output_path=str(output_path / 'shap_summary.png'))
    
    # Explain a sample prediction
    sample_explanation = explainer.explain_prediction(X, idx=0)
    
    return {
        'feature_importance': importance.to_dict('records'),
        'sample_explanation': sample_explanation,
        'plots': {
            'importance': str(output_path / 'shap_importance.png'),
            'summary': str(output_path / 'shap_summary.png')
        }
    }


if __name__ == "__main__":
    # Test the explainer
    import logging
    logging.basicConfig(level=logging.INFO)
    
    from models.prob_model import ProbModel
    
    # Load model and data
    try:
        model = ProbModel.load('outputs/prob_model.pkl')
        df = pd.read_csv('data/training_set.csv')
        
        feature_cols = [col for col in df.columns if FEATURE_PATTERN.match(col)]
        X = df[feature_cols]
        
        # Generate report
        report = generate_shap_report(model, X)
        
        print("\n=== Feature Importance ===")
        for item in report['feature_importance'][:5]:
            print(f"{item['feature']}: {item['importance_pct']:.1f}%")
            
    except FileNotFoundError as e:
        print(f"Required files not found: {e}")
