# Use Python 3.9
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system tools needed for AI libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file
COPY requirements.txt .

# Install all Python libraries
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# START THE APP (This replaces start.sh)
# We use a single command to run all 3 services at once
CMD python services/analysis/main.py & \
    python services/inference/main.py & \
    uvicorn services.gateway.main:app --host 0.0.0.0 --port 10000