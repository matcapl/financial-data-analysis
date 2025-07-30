FROM python:3.11-slim

# Install Node.js and Python prerequisites
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs tesseract-ocr poppler-utils python3-venv \
    && apt-get clean

WORKDIR /app

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Copy Python project files from repo root
COPY pyproject.toml poetry.lock ./

# Install Python dependencies via Poetry
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-dev --no-interaction --ansi

# Install server JS dependencies
COPY server/package*.json ./server/
RUN cd server && npm ci

# Copy server code, scripts, and client build
COPY server/ ./server/
COPY scripts/ ./scripts/

EXPOSE 8080

CMD ["node", "server/api/index.js"]
