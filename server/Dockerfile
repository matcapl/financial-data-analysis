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

# Install uv (single binary)
ADD https://astral.sh/uv/install.sh /install.sh
RUN sh /install.sh && rm /install.sh

# Set environment variables
ENV PYTHON_PATH=/usr/local/bin/python3
ENV ROOT_DIR=/app
ENV PYTHONPATH=/app/server/scripts:/app/server

WORKDIR /app

# Copy lock and manifest first (for caching layers)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Install Node.js deps
COPY server/package*.json ./server/
RUN npm install --prefix ./server

# Copy app code
COPY server/api ./server/api
COPY server/scripts ./server/scripts
COPY config ./config
COPY data ./data
COPY .env ./

# Expose and run
EXPOSE 4000
CMD ["node", "server/api/index.js"]
