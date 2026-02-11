# Multi-stage build for optimized production deployment
# Build stage for frontend
FROM node:18-alpine AS frontend-builder

WORKDIR /app/client

# Copy package files and install dependencies
# Frontend build requires devDependencies (react-scripts etc.)
COPY client/package*.json ./
RUN npm ci

# Copy frontend source code
COPY client/src ./src
COPY client/public ./public
COPY client/tsconfig.json ./
COPY client/tailwind.config.js ./
COPY client/postcss.config.js ./

# Build the React TypeScript application
RUN npm run build

# Production stage
FROM python:3.11-slim AS production

# Install system dependencies with minimal footprint
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        tesseract-ocr \
        poppler-utils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /tmp/* /var/tmp/*

# Install uv for faster dependency management
ARG UV_VERSION=0.7.6
RUN pip install --no-cache-dir uv==$UV_VERSION

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set environment variables
ENV PYTHON_PATH=/usr/local/bin/python3
ENV ROOT_DIR=/app
ENV PYTHONPATH=/app/server:/app
ENV PATH="/app/.venv/bin:$PATH"

# Set workdir
WORKDIR /app

# Copy and install Python dependencies first (better layer caching)
COPY requirements.txt uv.lock ./
RUN uv venv /app/.venv --seed && \
    /app/.venv/bin/pip install --no-cache-dir -r requirements.txt && \
    /app/.venv/bin/pip install --no-cache-dir python-multipart

# Copy application code in logical order
COPY config ./config
COPY database ./database
COPY scripts ./scripts
COPY server/ ./server/

# Copy built frontend from build stage
COPY --from=frontend-builder /app/client/build ./client/build

# Create required directories and set permissions
RUN mkdir -p uploads reports logs && \
    chown -R appuser:appuser /app

# Copy deployment script and make executable
COPY scripts/deploy-start.sh ./
RUN chmod +x deploy-start.sh

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:4000/health || exit 1

# Expose port
EXPOSE 4000

# Start application via deployment script
CMD ["./deploy-start.sh"]