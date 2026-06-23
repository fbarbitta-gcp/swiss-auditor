FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install API dependencies and Postgres adapter 
RUN pip install fastapi uvicorn pydantic psycopg2-binary httpx

# Copy strictly necessary logic
COPY app/tools_server.py ./app/

ENV PYTHONPATH=/app

# Run server
CMD ["uvicorn", "app.tools_server:app", "--host", "0.0.0.0", "--port", "8080"]
