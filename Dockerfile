FROM python:3.11-slim

WORKDIR /app

# Install dependencies directly
# We include requests explicitly to prevent yfinance errors
RUN pip install --no-cache-dir fastapi uvicorn pandas yfinance vaderSentiment requests

# Copy the ONE file
COPY app.py .

# Run the ONE command
CMD ["python", "app.py"]