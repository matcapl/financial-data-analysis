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

# Install Poetry
ARG POETRY_VERSION=2.1.4
ARG POETRY_CHECKSUM=963d56703976ce9cdc6ff460c44a4f8fbad64c110dc447b86eeabb4a47ec2160
RUN curl -fsSL https://install.python-poetry.org -o install-poetry.py \
 && echo "${POETRY_CHECKSUM}  install-poetry.py" | sha256sum -c - \
 && python3 install-poetry.py --version $POETRY_VERSION --yes \
 && ln -s /root/.local/bin/poetry /usr/local/bin/poetry \
 && rm install-poetry.py
ENV PATH="/root/.local/bin:$PATH"

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

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy Node.js package files and install dependencies
COPY server/package*.json ./server/
RUN npm install --prefix ./server

# Copy server code
COPY server/api ./server/api
COPY server/scripts ./server/scripts
COPY config ./config
COPY data ./data
COPY .env ./

# Expose and start
EXPOSE 4000
CMD ["node", "server/api/index.js"]