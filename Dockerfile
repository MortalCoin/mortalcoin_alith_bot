FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot code
COPY mortalcoin_bot/ ./mortalcoin_bot/
COPY mortalcoin_evm_cli/ ./mortalcoin_evm_cli/

# Copy the run script
COPY run_bot.py .

# Create directory for database
RUN mkdir -p /data

# Set environment variable for database path
ENV MORTALCOIN_DB_PATH=/data/mortalcoin_bot.db

# Run the bot
CMD ["python", "run_bot.py", "run"]