# Use Python 3.11 slim as base
FROM python:3.11-slim

# Install system dependencies: Node.js 18.x, Tesseract OCR, Poppler-utils, curl, ca-certificates
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        nodejs \
        npm \
        gnupg \
        lsb-release \
        tesseract-ocr \
        poppler-utils && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv
ARG UV_VERSION=0.7.6
RUN pip install --no-cache-dir uv==$UV_VERSION

# Setting environment variables
ENV PYTHON_PATH=/usr/local/bin/python3
ENV ROOT_DIR=/app
ENV PYTHONPATH=/app/server/scripts:/app/server

# Set workdir
WORKDIR /app

# Copy Python project files and install Python dependencies

# COPY pyproject.toml poetry.lock ./
# RUN poetry config virtualenvs.create false && \
#     poetry install --no-root --no-interaction --no-ansi

COPY requirements.txt uv.lock ./
RUN uv venv /app/.venv && \
    /app/.venv/bin/pip install --no-cache-dir -r requirements.txt
ENV PATH="/app/.venv/bin:$PATH"

# Copy Node.js package files and install dependencies
COPY server/package*.json ./server/
RUN npm install --prefix ./server

# Copy server code
COPY server/api ./server/api
COPY server/scripts ./server/scripts
COPY config ./config
COPY data ./data
COPY database ./database
COPY .env ./

# Expose and start
EXPOSE 4000
CMD ["node", "server/api/index.js"]