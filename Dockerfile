FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies required for building some python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code recursively (filtered by .dockerignore)
COPY . .

# Create directory for database
RUN mkdir -p /data

# Default path for DB inside container
ENV MORTALCOIN_DB_PATH=/data/mortalcoin_bot.db

# Default command
CMD ["python", "main.py", "run"]