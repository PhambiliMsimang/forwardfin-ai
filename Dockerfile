# Use Python 3.9
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the application code
COPY . .

# --- THE FIX ---
# We ignore requirements.txt and force-install the list directly here.
# This guarantees 'vaderSentiment' is installed.
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

# --- STARTUP COMMAND ---
# We use 'sh -c' to run multiple commands.
# We use 'python -m uvicorn' which is crash-proof (finds the module automatically).
CMD ["sh", "-c", "python services/analysis/main.py & python services/inference/main.py & python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 10000"]