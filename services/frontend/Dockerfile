FROM python:3.9-slim

WORKDIR /app

# Install Streamlit, Redis, AND Pandas
RUN pip install streamlit redis pandas

COPY main.py .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]