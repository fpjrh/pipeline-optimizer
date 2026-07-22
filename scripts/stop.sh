#!/bin/bash
PORT="${PORT:-8100}"
PID=$(lsof -ti :$PORT 2>/dev/null)
if [ -n "$PID" ]; then
    echo "Stopping Pipeline Optimizer (PID: $PID)..."
    kill "$PID"
    echo "Stopped."
else
    echo "No process found on port $PORT."
fi
