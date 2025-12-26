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

# Install dependencies (including supervisor)
RUN pip install --no-cache-dir -r requirements.txt

# Force install the AI tools (just to be safe)
RUN pip install --no-cache-dir vaderSentiment xgboost scikit-learn yfinance pandas numpy redis fastapi uvicorn requests supervisor

# Copy the app code
COPY . .

# Copy the supervisor configuration
COPY supervisord.conf /etc/supervisord.conf

# Start Supervisor (which starts your 3 apps)
CMD ["supervisord", "-c", "/etc/supervisord.conf"]