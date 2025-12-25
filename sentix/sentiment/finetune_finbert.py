"""
FinBERT Fine-tuning - Fine-tune FinBERT for Brazilian Portuguese.

This script provides utilities to fine-tune the FinBERT model on
Brazilian financial text for improved sentiment classification.

Usage:
    1. Prepare a CSV with 'text' and 'label' columns (0=neg, 1=neu, 2=pos)
    2. Run: python finetune_finbert.py --data path/to/data.csv

Note: Requires GPU for efficient training.
"""

from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np
from pathlib import Path
import logging
import argparse

logger = logging.getLogger(__name__)

# Check for transformers and datasets
try:
    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification,
        TrainingArguments,
        Trainer,
        DataCollatorWithPadding
    )
    from datasets import Dataset
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("transformers/datasets not available. Install with: pip install transformers datasets")


def load_training_data(csv_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load and split training data.
    
    Args:
        csv_path: Path to CSV with 'text' and 'label' columns.
        
    Returns:
        Tuple of (train_df, eval_df).
    """
    df = pd.read_csv(csv_path)
    
    # Validate columns
    required_cols = ['text', 'label']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"CSV must have column: {col}")
    
    # Clean data
    df = df.dropna(subset=['text', 'label'])
    df['text'] = df['text'].astype(str)
    df['label'] = df['label'].astype(int)
    
    # Split
    train_df = df.sample(frac=0.8, random_state=42)
    eval_df = df.drop(train_df.index)
    
    logger.info(f"Loaded {len(train_df)} training and {len(eval_df)} eval samples")
    
    return train_df, eval_df


def create_sample_dataset() -> pd.DataFrame:
    """
    Create a sample dataset for demonstration.
    
    This creates a small dataset of Brazilian financial news
    with sentiment labels for testing the fine-tuning pipeline.
    
    Returns:
        DataFrame with sample data.
    """
    samples = [
        # Positive (label=2)
        ("Petrobras anuncia lucro recorde no trimestre", 2),
        ("Ações da Vale sobem após resultados acima do esperado", 2),
        ("Investidores otimistas com recuperação da economia", 2),
        ("PIB brasileiro cresce acima das expectativas", 2),
        ("Banco Central sinaliza corte de juros", 2),
        ("Ibovespa renova máxima histórica", 2),
        ("Empresas brasileiras atraem recorde de investimentos", 2),
        
        # Negative (label=0)
        ("Bolsa cai com temores de recessão global", 0),
        ("Inflação surpreende e preocupa economistas", 0),
        ("Ações despencam após balanço negativo", 0),
        ("Risco fiscal pressiona dólar e juros futuros", 0),
        ("Desemprego volta a subir no Brasil", 0),
        ("Copom indica alta de juros na próxima reunião", 0),
        ("Empresas registram queda nas receitas", 0),
        
        # Neutral (label=1)
        ("Mercado aguarda decisão do Fed sobre juros", 1),
        ("Analistas mantêm projeções para o PIB", 1),
        ("Dólar opera estável nesta segunda-feira", 1),
        ("Resultados da empresa em linha com o esperado", 1),
        ("Banco divulga relatório trimestral", 1),
        ("Governo anuncia nova medida econômica", 1),
        ("Índice de confiança permanece estável", 1),
    ]
    
    return pd.DataFrame(samples, columns=['text', 'label'])


class FinBertFineTuner:
    """
    Fine-tuning utility for FinBERT on Portuguese text.
    
    Example:
        >>> finetuner = FinBertFineTuner()
        >>> finetuner.train('data/sentiment_labels.csv')
        >>> finetuner.save('models/finbert-ptbr')
    """
    
    def __init__(
        self,
        base_model: str = "ProsusAI/finbert",
        max_length: int = 128,
        device: Optional[str] = None
    ):
        """
        Initialize the fine-tuner.
        
        Args:
            base_model: HuggingFace model ID for base model.
            max_length: Maximum sequence length.
            device: Device for training (cuda/cpu).
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers and datasets required for fine-tuning")
        
        self.base_model = base_model
        self.max_length = max_length
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        
        logger.info(f"Loading tokenizer and model from {base_model}")
        self.tokenizer = AutoTokenizer.from_pretrained(base_model)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            base_model,
            num_labels=3  # neg, neu, pos
        )
        self.model.to(self.device)
        
        self.trainer = None
    
    def _tokenize(self, examples: Dict) -> Dict:
        """Tokenize examples."""
        return self.tokenizer(
            examples['text'],
            truncation=True,
            max_length=self.max_length,
            padding=False
        )
    
    def _prepare_dataset(self, df: pd.DataFrame) -> Dataset:
        """Convert DataFrame to HuggingFace Dataset."""
        dataset = Dataset.from_pandas(df[['text', 'label']])
        dataset = dataset.map(self._tokenize, batched=True)
        return dataset
    
    def train(
        self,
        train_df: pd.DataFrame,
        eval_df: pd.DataFrame,
        output_dir: str = 'outputs/finbert-ptbr',
        epochs: int = 3,
        batch_size: int = 16,
        learning_rate: float = 2e-5
    ) -> Dict[str, Any]:
        """
        Fine-tune the model.
        
        Args:
            train_df: Training data DataFrame.
            eval_df: Evaluation data DataFrame.
            output_dir: Directory for checkpoints.
            epochs: Number of training epochs.
            batch_size: Training batch size.
            learning_rate: Learning rate.
            
        Returns:
            Training metrics.
        """
        # Prepare datasets
        train_dataset = self._prepare_dataset(train_df)
        eval_dataset = self._prepare_dataset(eval_df)
        
        # Data collator
        data_collator = DataCollatorWithPadding(self.tokenizer)
        
        # Training arguments
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            learning_rate=learning_rate,
            weight_decay=0.01,
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            logging_dir=f"{output_dir}/logs",
            logging_steps=10,
            seed=42
        )
        
        # Create trainer
        self.trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            tokenizer=self.tokenizer,
            data_collator=data_collator
        )
        
        # Train
        logger.info("Starting fine-tuning...")
        train_result = self.trainer.train()
        
        # Evaluate
        eval_result = self.trainer.evaluate()
        
        logger.info(f"Training complete. Loss: {train_result.training_loss:.4f}")
        
        return {
            'train_loss': train_result.training_loss,
            'eval_loss': eval_result.get('eval_loss'),
            'epochs': epochs
        }
    
    def save(self, output_path: str) -> None:
        """
        Save the fine-tuned model.
        
        Args:
            output_path: Directory to save the model.
        """
        Path(output_path).mkdir(parents=True, exist_ok=True)
        
        self.model.save_pretrained(output_path)
        self.tokenizer.save_pretrained(output_path)
        
        logger.info(f"Model saved to {output_path}")
    
    def predict(self, texts: List[str]) -> np.ndarray:
        """
        Predict sentiment for texts.
        
        Args:
            texts: List of texts to classify.
            
        Returns:
            Array of probabilities (n_samples x 3).
        """
        self.model.eval()
        
        inputs = self.tokenizer(
            texts,
            truncation=True,
            max_length=self.max_length,
            padding=True,
            return_tensors='pt'
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.softmax(outputs.logits, dim=1).cpu().numpy()
        
        return probs


def main():
    """Main entry point for fine-tuning."""
    parser = argparse.ArgumentParser(description='Fine-tune FinBERT for PT-BR')
    parser.add_argument('--data', type=str, help='Path to training CSV')
    parser.add_argument('--output', type=str, default='outputs/finbert-ptbr',
                        help='Output directory')
    parser.add_argument('--epochs', type=int, default=3, help='Training epochs')
    parser.add_argument('--batch-size', type=int, default=16, help='Batch size')
    parser.add_argument('--demo', action='store_true', help='Run demo with sample data')
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    if args.demo or args.data is None:
        logger.info("Using sample dataset for demonstration")
        df = create_sample_dataset()
        train_df = df.sample(frac=0.8, random_state=42)
        eval_df = df.drop(train_df.index)
    else:
        train_df, eval_df = load_training_data(args.data)
    
    # Fine-tune
    finetuner = FinBertFineTuner()
    results = finetuner.train(
        train_df, eval_df,
        output_dir=args.output,
        epochs=args.epochs,
        batch_size=args.batch_size
    )
    
    # Save
    finetuner.save(args.output)
    
    # Test prediction
    test_texts = [
        "Petrobras anuncia aumento de dividendos",
        "Inflação acelera e preocupa mercado"
    ]
    probs = finetuner.predict(test_texts)
    
    print("\n=== Test Predictions ===")
    for text, prob in zip(test_texts, probs):
        sentiment = ['Negativo', 'Neutro', 'Positivo'][prob.argmax()]
        print(f"'{text}' -> {sentiment} ({prob.max():.2%})")


if __name__ == "__main__":
    main()
