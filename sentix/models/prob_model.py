"""
ProbModel - Calibrated probability model for sentiment-based predictions.

This module provides a logistic regression model with isotonic calibration
for predicting the probability of positive price movements based on
sentiment features.
"""

from typing import List, Optional
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
import pickle
import re
import logging

logger = logging.getLogger(__name__)

# Feature selection pattern
FEATURE_PATTERN = re.compile(r'(mean|std|min|max|count|unc|decay)')


class ProbModel:
    """
    Calibrated probability model for sentiment-based price prediction.
    
    This class wraps a LogisticRegression model inside CalibratedClassifierCV
    with isotonic calibration for better probability estimates.
    
    Attributes:
        model: The calibrated classifier.
        feature_cols: List of feature column names used during training.
        
    Example:
        >>> model = ProbModel()
        >>> model.fit(X_train, y_train)
        >>> probabilities = model.predict_proba(X_test)
    """
    
    def __init__(self) -> None:
        """Initialize the calibrated probability model."""
        self.model: CalibratedClassifierCV = CalibratedClassifierCV(
            LogisticRegression(random_state=42, max_iter=1000),
            method='isotonic',
            cv=3
        )
        # Preserve feature columns/order used in training
        self.feature_cols: Optional[List[str]] = None
        
    def fit(self, X: pd.DataFrame, y: pd.Series) -> 'ProbModel':
        """
        Fit the model on training data.
        
        Args:
            X: Feature DataFrame. NaN values will be filled with 0.
            y: Binary target series (0 or 1).
            
        Returns:
            Self for method chaining.
        """
        X = X.fillna(0)
        # Store feature order for consistent predictions
        self.feature_cols = X.columns.tolist()
        
        logger.info(f"Training ProbModel with {len(X)} samples and {len(self.feature_cols)} features")
        self.model.fit(X, y)
        
        return self

    def _select_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Select and order features according to training configuration.
        
        Args:
            X: Input feature DataFrame.
            
        Returns:
            DataFrame with features in correct order, with missing
            features filled with 0.
        """
        if self.feature_cols:
            return X.reindex(columns=self.feature_cols, fill_value=0)
        
        # Fallback: select features by regex pattern
        feature_cols = [col for col in X.columns if FEATURE_PATTERN.match(col)]
        return X[feature_cols].fillna(0)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict probability of positive class.
        
        Args:
            X: Feature DataFrame. Will be filtered and ordered to match
               training features.
               
        Returns:
            Array of probabilities for positive class (P(y=1)).
        """
        X_sel = self._select_features(X).fillna(0)
        return self.model.predict_proba(X_sel)[:, 1]
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict binary class labels.
        
        Args:
            X: Feature DataFrame.
            
        Returns:
            Array of binary predictions (0 or 1).
        """
        probas = self.predict_proba(X)
        return (probas >= 0.5).astype(int)

    @staticmethod
    def train_and_save(dataset_csv: str, model_path: str) -> 'ProbModel':
        """
        Train a model from CSV data and save to file.
        
        Args:
            dataset_csv: Path to training data CSV.
                        Must have 'y' column and feature columns.
            model_path: Path to save the trained model (.pkl).
            
        Returns:
            Trained ProbModel instance.
            
        Example:
            >>> model = ProbModel.train_and_save('data/training_set.csv', 'outputs/prob_model.pkl')
        """
        logger.info(f"Loading training data from {dataset_csv}")
        df = pd.read_csv(dataset_csv)
        
        # Select feature columns
        feature_cols = [col for col in df.columns if FEATURE_PATTERN.match(col)]
        X = df[feature_cols]
        y = df['y']
        
        logger.info(f"Training model with features: {feature_cols}")
        model = ProbModel()
        model.fit(X, y)
        model.feature_cols = feature_cols

        # Save model
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        logger.info(f"Model saved to {model_path}")
        
        return model

    @staticmethod
    def load(model_path: str) -> 'ProbModel':
        """
        Load a trained model from file.
        
        Args:
            model_path: Path to the saved model (.pkl).
            
        Returns:
            Loaded ProbModel instance.
            
        Raises:
            FileNotFoundError: If model_path doesn't exist.
            pickle.UnpicklingError: If file is corrupted.
        """
        logger.info(f"Loading model from {model_path}")
        with open(model_path, 'rb') as f:
            return pickle.load(f)