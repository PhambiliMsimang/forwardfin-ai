# Use Python 3.9
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy everything
COPY . .

# Force Python to look in /app for modules
ENV PYTHONPATH=/app

# Install all dependencies manually (No requirements.txt needed)
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

# Run the Unified Manager
CMD ["python", "unified.py"]