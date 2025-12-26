#!/bin/bash
echo "🚀 STARTING SERVICES..."
python services/analysis/main.py &
python services/inference/main.py &
uvicorn services.gateway.main:app --host 0.0.0.0 --port 10000