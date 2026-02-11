# Use Python 3.11 slim as base
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        tesseract-ocr \
        poppler-utils && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv via pip so it's available in /usr/local/bin
RUN python3 -m pip install --no-cache-dir uv

# Set environment variables
ENV PYTHON_PATH=/usr/local/bin/python3
ENV ROOT_DIR=/app
ENV PYTHONPATH=/app/server/app:/app/server

WORKDIR /app

# Copy dependency manifests for caching layers
COPY pyproject.toml uv.lock ./

# Install Python dependencies (production only)
RUN uv sync --frozen --no-dev

# Copy application code
COPY server ./server
COPY database ./database
COPY config ./config
COPY scripts ./scripts
COPY data ./data
COPY .env ./

# Expose service port
EXPOSE 4000

# Default command (FastAPI)
CMD ["/app/.venv/bin/python", "server/main.py"]
