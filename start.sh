#!/bin/bash

# 1. Start Redis (The Memory)
echo "Starting Redis..."
redis-server --daemonize yes

# 2. Start the Backend Robots (in the background)
echo "Starting Ingestion..."
python services/ingestion/main.py &

echo "Starting Analysis..."
python services/analysis/main.py &

echo "Starting Inference..."
python services/inference/main.py &

echo "Starting Narrative..."
python services/narrative/main.py &

# 3. Start the Frontend (The Face)
# We don't use '&' here because we want this to keep the container running
echo "Starting Frontend..."
streamlit run services/frontend/main.py --server.port $PORT --server.address 0.0.0.0