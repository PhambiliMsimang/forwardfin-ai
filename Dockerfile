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

# --- THE FIX ---
# We use the raw "Shell Form" (no brackets).
# This runs the backend services in the background (&) and the website in the foreground.
# If the website crashes, the whole container will exit immediately (showing us the error),
# instead of timing out after 10 minutes.
CMD python services/analysis/main.py & python services/inference/main.py & uvicorn services.gateway.main:app --host 0.0.0.0 --port 10000