# Use Python 3.9
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install dependencies (Standard)
RUN pip install --no-cache-dir -r requirements.txt

# FORCE INSTALL dependencies (Safety Net)
RUN pip install --no-cache-dir vaderSentiment xgboost scikit-learn yfinance pandas numpy redis fastapi uvicorn requests

# Copy the app code
COPY . .

# Start the app using our new Python script (Crash Proof)
CMD ["python", "run.py"]