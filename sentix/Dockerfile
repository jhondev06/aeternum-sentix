# Sentix API Dockerfile
# Multi-stage build for optimized image

# ==========================================================================
# Stage 1: Base Python image with dependencies
# ==========================================================================
FROM python:3.11-slim as base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==========================================================================
# Stage 2: Production image
# ==========================================================================
FROM python:3.11-slim as production

WORKDIR /app

# Copy installed packages from base
COPY --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base /usr/local/bin /usr/local/bin

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 sentix
RUN mkdir -p /app/data /app/outputs /app/logs && chown -R sentix:sentix /app

# Copy application code
COPY --chown=sentix:sentix . .

# Switch to non-root user
USER sentix

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command: run API
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]