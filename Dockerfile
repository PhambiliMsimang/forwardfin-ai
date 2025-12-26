# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (needed for some Python tools)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# 1. Install standard requirements
RUN pip install --no-cache-dir -r requirements.txt

# 2. FORCE INSTALL the missing AI tools (This fixes your issue)
RUN pip install --no-cache-dir vaderSentiment xgboost scikit-learn yfinance pandas numpy redis fastapi uvicorn requests

# Copy the rest of the application code
COPY . .

# Make the start script executable
RUN chmod +x start.sh

# Run the start script
CMD ["./start.sh"]