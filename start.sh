#!/bin/bash

# 1. Start Redis (The Memory)
echo "--- Starting Redis ---"
redis-server --daemonize yes
sleep 2

# 2. Start the Unified Backend (The Megabot)
# This runs Ingestion, Analysis, Inference, and Narrative in ONE process
echo "--- Starting Unified Backend ---"
python services/unified.py &
sleep 5

# 3. Start the Frontend (The Face)
echo "--- Starting Frontend ---"
streamlit run services/frontend/main.py --server.port $PORT --server.address 0.0.0.0