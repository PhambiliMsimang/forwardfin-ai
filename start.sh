#!/bin/bash

echo "🚀 STARTUP: Force-installing AI tools..."
pip install --upgrade pip
pip install vaderSentiment xgboost scikit-learn yfinance pandas numpy redis fastapi uvicorn requests

echo "✅ INSTALL COMPLETE. Starting Services..."

# Start the Backend Services in the background
python services/analysis/main.py &
python services/inference/main.py &

# Start the Frontend (Main Entrypoint)
uvicorn services.gateway.main:app --host 0.0.0.0 --port 10000