FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./

# All user files (CSV, videos.json, categories.json) live in /data
WORKDIR /data
