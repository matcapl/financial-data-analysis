# Use Python 3.11 slim as base
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg \
        lsb-release \
        tesseract-ocr \
        poppler-utils \
        nodejs \
        npm && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv via pip so it's available in /usr/local/bin
RUN python3 -m pip install --no-cache-dir uv

# Set environment variables
ENV PYTHON_PATH=/usr/local/bin/python3
ENV ROOT_DIR=/app
ENV PYTHONPATH=/app/server/scripts:/app/server

WORKDIR /app

# Copy dependency manifests for caching layers
COPY pyproject.toml uv.lock ./

# Install Python dependencies (production only)
RUN uv sync --frozen --no-dev

# Install Node.js dependencies
COPY server/package*.json ./server/
RUN npm install --prefix ./server

# Copy application code
COPY server/api ./server/api
COPY server/scripts ./server/scripts
COPY config ./config
COPY data ./data
COPY .env ./

# Expose service port
EXPOSE 4000

# Default command
CMD ["node", "server/api/index.js"]
