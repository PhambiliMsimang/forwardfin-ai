# We use a version of Python that is easy to build on
FROM python:3.9-slim

# Force Python to print instantly
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Install system tools needed to build TA-Lib (The tricky part!)
RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    wget \
    tar \
    && rm -rf /var/lib/apt/lists/*

# 2. Download and Compile TA-Lib C-Library
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install

# 3. Install Python Libraries (including the wrapper for TA-Lib)
RUN pip install redis asyncio numpy ta-lib

COPY main.py .

CMD ["python", "main.py"]