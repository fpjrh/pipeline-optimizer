#!/bin/bash
cd "$(dirname "$0")/.." || exit 1

if [ ! -f .env ]; then
    echo "No .env file found. Copy .env.example to .env and configure it."
    exit 1
fi

source .env 2>/dev/null

PORT="${PORT:-8100}"
HOST="${HOST:-0.0.0.0}"

echo "Starting Pipeline Optimizer on ${HOST}:${PORT}..."
uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
