#!/bin/bash

# 1. Start Redis (Low Memory)
echo "--- Starting Redis ---"
redis-server --daemonize yes
sleep 2  # Give it a moment

# 2. Start Ingestion (Fetches Data)
echo "--- Starting Ingestion Service ---"
python services/ingestion/main.py &
sleep 2

# 3. Start Analysis (Math)
echo "--- Starting Analysis Engine ---"
python services/analysis/main.py &
sleep 2

# 4. Start Inference (The Heavy Brain)
# We give this one extra time to load XGBoost
echo "--- Starting AI Inference ---"
python services/inference/main.py &
sleep 5

# 5. Start Narrative (The Writer)
echo "--- Starting Narrative Service ---"
python services/narrative/main.py &
sleep 2

# 6. Start Frontend (The Face)
echo "--- Starting Frontend ---"
streamlit run services/frontend/main.py --server.port $PORT --server.address 0.0.0.0