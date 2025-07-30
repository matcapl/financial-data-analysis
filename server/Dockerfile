FROM python:3.11-slim
WORKDIR /app
COPY server/ /app/
RUN pip install --no-cache-dir -r requirements.txt
RUN npm ci --prefix .
CMD ["node", "api/index.js"]
