# Use Python 3.9
FROM python:3.9-slim

# Set working directory to /app
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy everything (including your new __init__.py files)
COPY . .

# Force Python to look in the current directory
ENV PYTHONPATH=/app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    redis \
    xgboost \
    pandas \
    numpy \
    yfinance \
    scikit-learn \
    vaderSentiment \
    requests

# Start the apps
# We use the raw command string which is most reliable
CMD sh -c "python services/analysis/main.py & python services/inference/main.py & uvicorn services.gateway.main:app --host 0.0.0.0 --port 10000"