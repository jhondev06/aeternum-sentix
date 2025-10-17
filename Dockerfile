# Root-level Dockerfile for Render builds
# This Dockerfile copies application code from the sentix/ subdirectory

FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from sentix/
COPY sentix/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code from sentix/
COPY sentix/ .

# Create necessary directories and set caches for model downloads
RUN mkdir -p data outputs logs/alerts
ENV TRANSFORMERS_CACHE=/app/data/hf-cache
ENV HF_HOME=/app/data/hf-home
ENV TORCH_HOME=/app/data/torch

# Expose port (Render sets PORT env)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Start app (initialize demo data/model if missing on mounted disk)
CMD ["sh", "-c", "if [ ! -f data/sentiment_bars.csv ] || [ ! -f outputs/prob_model.pkl ]; then python init_model.py; fi && uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]