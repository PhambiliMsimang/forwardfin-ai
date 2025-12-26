FROM python:3.9-slim

WORKDIR /app

# Install dependencies directly (No requirements.txt needed)
RUN pip install --no-cache-dir fastapi uvicorn redis pandas numpy yfinance vaderSentiment requests

# Copy the ONE file we need
COPY app.py .

# Run it
CMD ["python", "app.py"]