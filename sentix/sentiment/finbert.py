import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import pandas as pd
import numpy as np

class FinBertSentiment:
    def __init__(self, model_id: str, batch_size: int = 16, device: str = None):
        torch.manual_seed(42)
        np.random.seed(42)

        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_id)
        self.device = device if device else ('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        self.model.eval()
        self.batch_size = batch_size

    def predict_batch(self, texts: list[str]) -> pd.DataFrame:
        results = []
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i+self.batch_size]
            batch_results = self._predict_single_batch(batch_texts)
            results.extend(batch_results)

        return pd.DataFrame(results, columns=['pos', 'neg', 'neu', 'score'])

    def _predict_single_batch(self, texts: list[str]) -> list:
        # Tokenize entire batch at once for performance
        inputs = self.tokenizer(
            texts,
            truncation=True,
            max_length=256,
            padding=True,
            return_tensors='pt'
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs_batch = torch.softmax(logits, dim=1).cpu().numpy()

        batch_results = []
        for i, text in enumerate(texts):
            if not text or not text.strip():
                batch_results.append([0.0, 0.0, 1.0, 0.0])
                continue
            # Assuming order: neg, neu, pos (FinBERT: neg, neu, pos)
            neg, neu, pos = probs_batch[i]
            score = pos - neg
            batch_results.append([pos, neg, neu, score])

        return batch_results