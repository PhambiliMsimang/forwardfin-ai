# Use a slightly larger version of Python that mimics a full computer
FROM python:3.10-slim

# Prevent Python from writing temporary files
ENV PYTHONUNBUFFERED=1

# Create the app folder
WORKDIR /app

# 1. Install System Tools (Redis, gcc for AI, git)
RUN apt-get update && apt-get install -y \
    redis-server \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python Libraries (All of them!)
RUN pip install --no-cache-dir \
    redis \
    asyncio \
    yfinance \
    pandas \
    numpy \
    xgboost \
    shap \
    scikit-learn \
    streamlit

# 3. Copy your entire project code into the container
COPY . .

# 4. Give the "Bus Driver" permission to drive
RUN chmod +x start.sh

# 5. The Cloud will tell us which port to use (default to 8501)
ENV PORT=8501

# 6. Start the Bus!
CMD ["./start.sh"]