"""
Tests for the prob_model module.
"""

import pytest
import pandas as pd
import numpy as np
import os
import tempfile

from models.prob_model import ProbModel, FEATURE_PATTERN


class TestFeaturePattern:
    """Tests for the feature selection pattern."""
    
    def test_matches_expected_columns(self):
        """Test that pattern matches expected feature columns."""
        valid_cols = ['mean_sent', 'std_sent', 'min_sent', 'max_sent', 
                      'count', 'unc_mean', 'time_decay_mean']
        
        for col in valid_cols:
            assert FEATURE_PATTERN.match(col), f"Pattern should match {col}"
    
    def test_rejects_invalid_columns(self):
        """Test that pattern rejects non-feature columns."""
        invalid_cols = ['ticker', 'bucket_start', 'close', 'y', 'r_fwd']
        
        for col in invalid_cols:
            assert not FEATURE_PATTERN.match(col), f"Pattern should not match {col}"


class TestProbModel:
    """Tests for ProbModel class."""
    
    def test_init(self):
        """Test model initialization."""
        model = ProbModel()
        
        assert model.model is not None
        assert model.feature_cols is None
    
    def test_fit(self, sample_training_df):
        """Test model fitting."""
        feature_cols = [col for col in sample_training_df.columns if FEATURE_PATTERN.match(col)]
        X = sample_training_df[feature_cols]
        y = sample_training_df['y']
        
        model = ProbModel()
        result = model.fit(X, y)
        
        assert result is model  # Should return self
        assert model.feature_cols == feature_cols
    
    def test_predict_proba(self, sample_training_df):
        """Test probability predictions."""
        feature_cols = [col for col in sample_training_df.columns if FEATURE_PATTERN.match(col)]
        X = sample_training_df[feature_cols]
        y = sample_training_df['y']
        
        model = ProbModel()
        model.fit(X, y)
        
        probas = model.predict_proba(X)
        
        assert len(probas) == len(X)
        assert all(0 <= p <= 1 for p in probas)
    
    def test_predict(self, sample_training_df):
        """Test binary predictions."""
        feature_cols = [col for col in sample_training_df.columns if FEATURE_PATTERN.match(col)]
        X = sample_training_df[feature_cols]
        y = sample_training_df['y']
        
        model = ProbModel()
        model.fit(X, y)
        
        preds = model.predict(X)
        
        assert len(preds) == len(X)
        assert all(p in [0, 1] for p in preds)
    
    def test_select_features_with_stored_cols(self, sample_training_df):
        """Test feature selection with stored columns."""
        feature_cols = [col for col in sample_training_df.columns if FEATURE_PATTERN.match(col)]
        X = sample_training_df[feature_cols]
        y = sample_training_df['y']
        
        model = ProbModel()
        model.fit(X, y)
        
        # Test with extra columns
        X_extra = X.copy()
        X_extra['extra_col'] = 1
        
        X_selected = model._select_features(X_extra)
        
        assert list(X_selected.columns) == feature_cols
    
    def test_handles_nan_values(self, sample_training_df):
        """Test handling of NaN values."""
        feature_cols = [col for col in sample_training_df.columns if FEATURE_PATTERN.match(col)]
        X = sample_training_df[feature_cols].copy()
        X.iloc[0, 0] = np.nan  # Introduce NaN
        y = sample_training_df['y']
        
        model = ProbModel()
        model.fit(X, y)
        
        probas = model.predict_proba(X)
        
        assert len(probas) == len(X)
        assert not any(np.isnan(probas))


class TestProbModelSaveLoad:
    """Tests for model persistence."""
    
    def test_train_and_save(self, sample_training_df, temp_dir):
        """Test training and saving model."""
        # Save training data
        csv_path = os.path.join(temp_dir, 'training.csv')
        sample_training_df.to_csv(csv_path, index=False)
        
        model_path = os.path.join(temp_dir, 'model.pkl')
        
        model = ProbModel.train_and_save(csv_path, model_path)
        
        assert os.path.exists(model_path)
        assert model.feature_cols is not None
    
    def test_load(self, sample_training_df, temp_dir):
        """Test loading a saved model."""
        # Save training data and train
        csv_path = os.path.join(temp_dir, 'training.csv')
        sample_training_df.to_csv(csv_path, index=False)
        model_path = os.path.join(temp_dir, 'model.pkl')
        
        original_model = ProbModel.train_and_save(csv_path, model_path)
        
        # Load and compare
        loaded_model = ProbModel.load(model_path)
        
        assert loaded_model.feature_cols == original_model.feature_cols
    
    def test_load_nonexistent_file(self):
        """Test that loading nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            ProbModel.load('nonexistent_model.pkl')
    
    def test_predictions_match_after_load(self, sample_training_df, temp_dir):
        """Test that loaded model produces same predictions."""
        # Prepare data
        feature_cols = [col for col in sample_training_df.columns if FEATURE_PATTERN.match(col)]
        X = sample_training_df[feature_cols]
        
        # Save and load
        csv_path = os.path.join(temp_dir, 'training.csv')
        sample_training_df.to_csv(csv_path, index=False)
        model_path = os.path.join(temp_dir, 'model.pkl')
        
        original_model = ProbModel.train_and_save(csv_path, model_path)
        loaded_model = ProbModel.load(model_path)
        
        # Compare predictions
        original_probas = original_model.predict_proba(X)
        loaded_probas = loaded_model.predict_proba(X)
        
        np.testing.assert_array_almost_equal(original_probas, loaded_probas)
