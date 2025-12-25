"""
Sentix FinBERT - Hugging Face Spaces
Sentiment Analysis API for Brazilian Financial News
"""

import gradio as gr
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import numpy as np
from typing import Dict, List, Tuple
import json

# =============================================================================
# Model Loading
# =============================================================================

MODEL_ID = "ProsusAI/finbert"

print("Loading FinBERT model...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID)
model.eval()

# Use GPU if available
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)
print(f"Model loaded on {device}")


# =============================================================================
# Prediction Functions
# =============================================================================

def predict_sentiment(text: str) -> Tuple[Dict[str, float], str, float]:
    """
    Analyze sentiment of financial text.
    
    Returns:
        Tuple of (probabilities dict, sentiment label, score)
    """
    if not text or not text.strip():
        return {"Positivo": 0.0, "Neutro": 1.0, "Negativo": 0.0}, "Neutro", 0.0
    
    # Tokenize
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True
    ).to(device)
    
    # Predict
    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=1).cpu().numpy()[0]
    
    # FinBERT order: negative, neutral, positive
    neg, neu, pos = probs
    
    # Score: pos - neg
    score = float(pos - neg)
    
    # Label
    if score > 0.15:
        label = "Positivo 📈"
    elif score < -0.15:
        label = "Negativo 📉"
    else:
        label = "Neutro ➖"
    
    probabilities = {
        "Positivo": float(pos),
        "Neutro": float(neu),
        "Negativo": float(neg)
    }
    
    return probabilities, label, score


def predict_batch(texts: str) -> str:
    """
    Analyze multiple texts (one per line).
    
    Returns JSON with results.
    """
    lines = [t.strip() for t in texts.strip().split('\n') if t.strip()]
    
    results = []
    for text in lines[:10]:  # Limit to 10
        probs, label, score = predict_sentiment(text)
        results.append({
            "text": text[:100] + "..." if len(text) > 100 else text,
            "label": label,
            "score": round(score, 4),
            "probabilities": {k: round(v, 4) for k, v in probs.items()}
        })
    
    return json.dumps(results, indent=2, ensure_ascii=False)


def api_predict(text: str) -> Dict:
    """
    API endpoint for external services.
    
    Returns dict with prediction.
    """
    probs, label, score = predict_sentiment(text)
    
    return {
        "text": text,
        "sentiment": label.replace(" 📈", "").replace(" 📉", "").replace(" ➖", ""),
        "score": round(score, 4),
        "probabilities": {
            "positive": round(probs["Positivo"], 4),
            "neutral": round(probs["Neutro"], 4),
            "negative": round(probs["Negativo"], 4)
        }
    }


# =============================================================================
# Gradio Interface
# =============================================================================

# Examples
examples = [
    ["Petrobras anuncia lucro recorde no trimestre e ações sobem 5%"],
    ["Inflação acelera e Banco Central deve elevar juros na próxima reunião"],
    ["Mercado aguarda decisão do COPOM sobre taxa Selic"],
    ["Vale reporta queda de 20% nas exportações de minério"],
    ["Ibovespa fecha em alta com otimismo sobre reforma tributária"],
]

# Single text interface
single_interface = gr.Interface(
    fn=predict_sentiment,
    inputs=gr.Textbox(
        label="Texto Financeiro",
        placeholder="Digite uma notícia ou texto financeiro...",
        lines=3
    ),
    outputs=[
        gr.Label(label="Probabilidades", num_top_classes=3),
        gr.Textbox(label="Sentimento"),
        gr.Number(label="Score (-1 a +1)")
    ],
    title="🇧🇷 Sentix FinBERT - Análise de Sentimento Financeiro",
    description="""
    Analise o sentimento de notícias financeiras brasileiras usando FinBERT.
    
    **Score:** -1 (muito negativo) a +1 (muito positivo)
    
    💡 **Dica:** Use textos de notícias sobre ações, economia, juros, etc.
    """,
    examples=examples,
    theme=gr.themes.Soft()
)

# Batch interface
batch_interface = gr.Interface(
    fn=predict_batch,
    inputs=gr.Textbox(
        label="Textos (um por linha)",
        placeholder="Texto 1\nTexto 2\nTexto 3",
        lines=8
    ),
    outputs=gr.JSON(label="Resultados"),
    title="📊 Análise em Lote",
    description="Analise múltiplos textos de uma vez (máximo 10)."
)

# API interface
api_interface = gr.Interface(
    fn=api_predict,
    inputs=gr.Textbox(label="Texto"),
    outputs=gr.JSON(label="Resposta API"),
    title="🔌 API Endpoint",
    description="""
    Use esta interface para integrar com outros serviços.
    
    **Endpoint:** `POST /api/predict`
    
    ```python
    import requests
    response = requests.post(
        "https://seu-space.hf.space/api/predict",
        json={"data": ["seu texto aqui"]}
    )
    ```
    """
)

# Combine interfaces
demo = gr.TabbedInterface(
    [single_interface, batch_interface, api_interface],
    ["Análise Única", "Análise em Lote", "API"],
    title="Sentix FinBERT"
)

# Launch
if __name__ == "__main__":
    demo.launch()
