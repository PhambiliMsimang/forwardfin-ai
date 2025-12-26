# Use Python 3.9
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the application code first
COPY . .

# --- FIX 1: THE MAP ---
# This tells Python: "Look for code inside the /app folder"
ENV PYTHONPATH=/app

# --- FIX 2: THE GLUE ---
# We create empty files called __init__.py. 
# This tells Python: "These folders contain importable code."
RUN touch services/__init__.py && \
    touch services/gateway/__init__.py && \
    touch services/analysis/__init__.py && \
    touch services/inference/__init__.py

# Install dependencies (Force install everything)
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
    requests \
    supervisor

# --- STARTUP ---
# We use the same command, but now Python knows where 'services.gateway' is.
CMD ["sh", "-c", "python services/analysis/main.py & python services/inference/main.py & python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 10000"]