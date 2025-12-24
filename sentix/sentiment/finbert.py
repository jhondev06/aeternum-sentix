"""
FinBERT Sentiment Analysis - Financial sentiment classification using transformers.

This module provides a wrapper around the FinBERT model for batch sentiment
prediction on financial text.
"""

from typing import List, Tuple, Optional
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, PreTrainedTokenizer, PreTrainedModel
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class FinBertSentiment:
    """
    FinBERT-based sentiment analyzer for financial text.
    
    This class wraps the ProsusAI/finbert model to provide batch predictions
    with positive, negative, and neutral scores.
    
    Attributes:
        tokenizer: HuggingFace tokenizer for the model.
        model: The FinBERT model.
        device: Device for inference (cuda/cpu).
        batch_size: Number of texts to process per batch.
        
    Example:
        >>> sentiment = FinBertSentiment("ProsusAI/finbert", batch_size=16)
        >>> results = sentiment.predict_batch(["Stock prices surge on earnings"])
        >>> print(results['score'].iloc[0])  # Positive score
    """
    
    def __init__(
        self,
        model_id: str,
        batch_size: int = 16,
        device: Optional[str] = None
    ) -> None:
        """
        Initialize the FinBERT sentiment analyzer.
        
        Args:
            model_id: HuggingFace model identifier (e.g., "ProsusAI/finbert").
            batch_size: Number of texts to process per batch.
            device: Device for inference. If None, auto-selects CUDA if available.
        """
        # Set seeds for determinism
        torch.manual_seed(42)
        np.random.seed(42)

        logger.info(f"Loading FinBERT model: {model_id}")
        self.tokenizer: PreTrainedTokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model: PreTrainedModel = AutoModelForSequenceClassification.from_pretrained(model_id)
        self.device: str = device if device else ('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        self.model.eval()
        self.batch_size: int = batch_size
        logger.info(f"FinBERT loaded on device: {self.device}")

    def predict_batch(self, texts: List[str]) -> pd.DataFrame:
        """
        Predict sentiment for a batch of texts.
        
        Args:
            texts: List of text strings to analyze.
            
        Returns:
            DataFrame with columns:
                - pos: Positive sentiment probability
                - neg: Negative sentiment probability
                - neu: Neutral sentiment probability
                - score: Net sentiment score (pos - neg)
                
        Note:
            Empty or None texts return neu=1.0, score=0.0.
        """
        results: List[Tuple[float, float, float, float]] = []
        
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]
            batch_results = self._predict_single_batch(batch_texts)
            results.extend(batch_results)

        return pd.DataFrame(results, columns=['pos', 'neg', 'neu', 'score'])

    def _predict_single_batch(self, texts: List[str]) -> List[Tuple[float, float, float, float]]:
        """
        Process a single batch of texts through the model.
        
        Args:
            texts: List of texts (max batch_size items).
            
        Returns:
            List of tuples (pos, neg, neu, score) for each text.
        """
        # Pre-process: handle empty texts
        processed_texts: List[str] = []
        empty_indices: set = set()
        
        for i, text in enumerate(texts):
            if not text or not str(text).strip():
                processed_texts.append("neutral")  # Placeholder for empty
                empty_indices.add(i)
            else:
                processed_texts.append(str(text))
        
        # Tokenize entire batch at once for performance
        inputs = self.tokenizer(
            processed_texts,
            truncation=True,
            max_length=256,
            padding=True,
            return_tensors='pt'
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs_batch = torch.softmax(logits, dim=1).cpu().numpy()

        batch_results: List[Tuple[float, float, float, float]] = []
        
        for i in range(len(texts)):
            if i in empty_indices:
                # Return neutral for empty texts
                batch_results.append((0.0, 0.0, 1.0, 0.0))
                continue
                
            # FinBERT output order: neg, neu, pos (index 0, 1, 2)
            neg, neu, pos = probs_batch[i]
            score = float(pos - neg)
            batch_results.append((float(pos), float(neg), float(neu), score))

        return batch_results
    
    def predict_single(self, text: str) -> dict:
        """
        Predict sentiment for a single text.
        
        Args:
            text: Text string to analyze.
            
        Returns:
            Dictionary with keys: pos, neg, neu, score
        """
        result = self.predict_batch([text])
        return result.iloc[0].to_dict()