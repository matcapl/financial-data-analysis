FROM python:3.11-slim
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean
WORKDIR /app
COPY server/ /app/
RUN npm ci
EXPOSE 8080
CMD ["node", "api/index.js"]
