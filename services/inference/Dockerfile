FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (needed for some AI libraries)
RUN apt-get update && apt-get install -y \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install AI Libraries
# xgboost: The model
# shap: The explainability tool
# numpy: The math
# redis: The messaging
RUN pip install redis asyncio numpy xgboost shap scikit-learn

COPY main.py .

CMD ["python", "main.py"]