import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
import pickle
import re

class ProbModel:
    def __init__(self):
        self.model = CalibratedClassifierCV(
            LogisticRegression(random_state=42),
            method='isotonic'
        )
        # Preserva as colunas/ordem de features usadas no treino
        self.feature_cols = None
    def fit(self, X: pd.DataFrame, y: pd.Series):
        X = X.fillna(0)
        # Armazena a ordem das features para uso consistente na predição
        self.feature_cols = X.columns.tolist()
        self.model.fit(X, y)

    def _select_features(self, X: pd.DataFrame) -> pd.DataFrame:
        """Seleciona e ordena as features de X conforme o treino, com fallback por regex."""
        if self.feature_cols:
            return X.reindex(columns=self.feature_cols, fill_value=0)
        feature_cols = [col for col in X.columns if re.match(r'(mean|std|min|max|count|unc|decay)', col)]
        return X[feature_cols].fillna(0)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X_sel = self._select_features(X).fillna(0)
        return self.model.predict_proba(X_sel)[:, 1]

    @staticmethod
    def train_and_save(dataset_csv: str, model_path: str):
        df = pd.read_csv(dataset_csv)
        feature_cols = [col for col in df.columns if re.match(r'(mean|std|min|max|count|unc|decay)', col)]
        X = df[feature_cols]
        y = df['y']

        model = ProbModel()
        model.fit(X, y)
        # Persiste as colunas/ordem das features
        model.feature_cols = feature_cols

        with open(model_path, 'wb') as f:
            pickle.dump(model, f)

    @staticmethod
    def load(model_path: str) -> 'ProbModel':
        with open(model_path, 'rb') as f:
            return pickle.load(f)