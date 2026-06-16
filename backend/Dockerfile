FROM python:3.11-slim

WORKDIR /app

# System deps for sentence-transformers and chromadb
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run knowledge-base ingestion at build time so the container starts fast
# If you update knowledge sources, rebuild the image or mount a volume.
RUN python -m scripts.ingest

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
