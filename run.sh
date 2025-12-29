#!/bin/bash

set -euo pipefail

# Ensure the current directory is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH:-.}:."

# Start Ollama model in background for vision processing
# Note: 'ollama run' starts an interactive session, but putting it in background
# might be intended to just ensure the model is loaded or the server is up.
# Ideally, ensure 'ollama serve' is running.
echo "Starting Ollama vision model..."
ollama run qwen3-vl:4b &
OLLAMA_PID=$!
sleep 2  # Give ollama time to start

# Function to cleanup on exit
cleanup() {
    echo "Cleaning up..."
    kill $OLLAMA_PID 2>/dev/null || true
}
trap cleanup EXIT

# Start the simulation (which includes the MCP server)
echo "Starting Spot Simulation..."
python main.py "$@"
