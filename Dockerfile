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

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app code
COPY . .

# --- THE MAGIC FIX ---
# We force the server to create a fresh start.sh file with LINUX line endings.
# This deletes any corrupted Windows version you might have uploaded.
RUN echo "#!/bin/bash" > start.sh
RUN echo "python services/analysis/main.py &" >> start.sh
RUN echo "python services/inference/main.py &" >> start.sh
RUN echo "uvicorn services.gateway.main:app --host 0.0.0.0 --port 10000" >> start.sh

# Make it executable
RUN chmod +x start.sh

# Run it
CMD ["./start.sh"]