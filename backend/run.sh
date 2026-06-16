#!/usr/bin/env bash
# run.sh – start the FastAPI server
# Usage: ./run.sh [--port 8080]

set -e
PORT=${1:-8000}

# Load .env if it exists
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

echo "Starting UML Generator API on port $PORT"
echo "LLM backend: ${LLM_BACKEND:-ollama}"

uvicorn api.main:app --host 0.0.0.0 --port "$PORT" --reload
