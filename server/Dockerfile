# Use Python 3.11 slim as base
FROM python:3.11-slim

# Install system dependencies: Node.js 18.x, Tesseract OCR, Poppler-utils, curl, ca-certificates
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl \
      ca-certificates \
      gnupg \
      lsb-release \
      tesseract-ocr \
      poppler-utils && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry

# Set workdir
WORKDIR /app

# Copy Python project files and install Python dependencies
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

# Copy Node.js package files and install dependencies
COPY server/package*.json ./server/
RUN npm install --prefix ./server

# Copy server code
COPY server/api ./server/api
COPY server/scripts ./server/scripts

# Expose and start
EXPOSE 8080
CMD ["node", "server/api/index.js"]
