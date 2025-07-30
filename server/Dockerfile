FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs tesseract-ocr poppler-utils \
    && apt-get install -y python3-venv && apt-get clean

WORKDIR /app

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Copy Python project files
COPY pyproject.toml poetry.lock ./

# Install Python dependencies
RUN ~/.local/bin/poetry config virtualenvs.create false \
    && ~/.local/bin/poetry install --no-dev --no-interaction --no-ansi

# Install Node.js dependencies
COPY server/package*.json ./server/
RUN cd server && npm ci

# Copy project files
COPY server/ ./server/
COPY scripts/ ./scripts/
COPY client/ ./client/
COPY schema/ ./schema/
COPY data/ ./data/

EXPOSE 8080

CMD ["node", "server/api/index.js"]
