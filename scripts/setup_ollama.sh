#!/bin/bash
# Setup script for Ollama and required models

echo "=== PYQ Analyzer - Ollama Setup ==="

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "Ollama is already installed"
fi

# Start Ollama service (if not running)
if ! pgrep -x "ollama" > /dev/null; then
    echo "Starting Ollama service..."
    ollama serve &
    sleep 5
fi

# Pull the required model
echo "Pulling Llama 3.2 3B model..."
ollama pull llama3.2:3b

echo ""
echo "=== Setup Complete ==="
echo "Ollama is ready with Llama 3.2 3B model"
echo "You can test it with: ollama run llama3.2:3b 'Hello'"
