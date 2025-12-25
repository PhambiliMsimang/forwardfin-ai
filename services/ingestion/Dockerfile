FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install Redis and Yahoo Finance
RUN pip install redis asyncio yfinance

COPY main.py .
CMD ["python", "main.py"]