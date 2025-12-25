"""
Sentix API Light - For Render Free Tier
Uses HuggingFace Space for sentiment analysis
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import httpx
from datetime import datetime

# =============================================================================
# Configuration
# =============================================================================

HF_SPACE_URL = os.environ.get("HF_SPACE_URL", "https://your-username-sentix-finbert.hf.space")

app = FastAPI(
    title="Sentix API Light",
    description="Sentiment Analysis API for Brazilian Financial News",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Models
# =============================================================================

class TextInput(BaseModel):
    text: str


class BatchInput(BaseModel):
    texts: List[str]


class SentimentResponse(BaseModel):
    text: str
    sentiment: str
    score: float
    probabilities: Dict[str, float]


# =============================================================================
# HuggingFace Client
# =============================================================================

async def analyze_with_hf(text: str) -> Dict[str, Any]:
    """Call HuggingFace Space API."""
    try:
        from gradio_client import Client
        
        client = Client(HF_SPACE_URL)
        result = client.predict(
            text=text,
            api_name="/predict"
        )
        
        probs, label, score = result
        
        return {
            "text": text,
            "sentiment": label.replace(" 📈", "").replace(" 📉", "").replace(" ➖", ""),
            "score": float(score),
            "probabilities": {
                "positive": probs.get("Positivo", 0),
                "neutral": probs.get("Neutro", 0),
                "negative": probs.get("Negativo", 0)
            }
        }
        
    except Exception as e:
        # Fallback
        return {
            "text": text,
            "sentiment": "unknown",
            "score": 0.0,
            "probabilities": {"positive": 0.33, "neutral": 0.34, "negative": 0.33},
            "error": str(e)
        }


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Sentix API Light",
        "version": "2.0.0",
        "status": "running",
        "hf_space": HF_SPACE_URL
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/predict", response_model=SentimentResponse)
async def predict_sentiment(input: TextInput):
    """
    Analyze sentiment of a single text.
    
    Uses HuggingFace Space API for FinBERT inference.
    """
    if not input.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    result = await analyze_with_hf(input.text)
    return result


@app.post("/predict/batch")
async def predict_batch(input: BatchInput):
    """
    Analyze sentiment of multiple texts.
    
    Limited to 10 texts per request.
    """
    if not input.texts:
        raise HTTPException(status_code=400, detail="Texts list cannot be empty")
    
    texts = input.texts[:10]  # Limit
    
    results = []
    for text in texts:
        if text.strip():
            result = await analyze_with_hf(text)
            results.append(result)
    
    return {"results": results, "count": len(results)}


@app.get("/stats")
async def get_stats():
    """Get API statistics."""
    return {
        "api_version": "2.0.0",
        "model": "FinBERT (via HuggingFace)",
        "hf_space": HF_SPACE_URL,
        "features": [
            "Single text analysis",
            "Batch analysis (up to 10)",
            "Probability scores"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
