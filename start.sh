#!/bin/bash

echo "🚀 STARTING SERVICES..."

# Start the Backend Services in the background
python services/analysis/main.py &
python services/inference/main.py &

# Start the Frontend (Main Entrypoint)
uvicorn services.gateway.main:app --host 0.0.0.0 --port 10000