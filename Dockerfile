FROM python:3.9-slim

WORKDIR /app

# Install minimal tools
RUN pip install --no-cache-dir fastapi uvicorn pandas yfinance vaderSentiment

# Copy the app
COPY app.py .

# Run the app
CMD ["python", "app.py"]