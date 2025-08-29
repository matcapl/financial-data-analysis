# Use Python 3.11 slim as base
FROM python:3.11-slim

# Install system dependencies: Tesseract OCR, Poppler-utils for PDF processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        tesseract-ocr \
        poppler-utils && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install uv
ARG UV_VERSION=0.7.6
RUN pip install --no-cache-dir uv==$UV_VERSION

# Setting environment variables
ENV PYTHON_PATH=/usr/local/bin/python3
ENV ROOT_DIR=/app
ENV PYTHONPATH=/app/server:/app

# Set workdir
WORKDIR /app

# Copy Python project files and install Python dependencies
COPY requirements.txt uv.lock ./
RUN uv venv /app/.venv && \
    /app/.venv/bin/pip install --no-cache-dir -r requirements.txt && \
    /app/.venv/bin/pip install --no-cache-dir python-multipart
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY server/ ./server/
COPY config ./config
COPY data ./data
COPY database ./database
COPY .env ./

# Create required directories
RUN mkdir -p uploads reports

# Expose port and start FastAPI
EXPOSE 4000
WORKDIR /app
CMD ["/app/.venv/bin/python", "server/main.py"]