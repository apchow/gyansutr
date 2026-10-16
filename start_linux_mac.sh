#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "==================================================="
echo "  GyanSutr - Sovereign Unified Trusted Retrieval"
echo "==================================================="

PYTHON_BIN="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_BIN="python"
fi

if [ ! -f "venv/bin/python" ]; then
    echo "[1/4] Creating local virtual environment..."
    $PYTHON_BIN -m venv venv
fi

echo "[2/4] Activating environment and checking dependencies..."
./venv/bin/python -m pip install --upgrade pip -q
./venv/bin/python -m pip install -r requirements.txt -q

echo "[3/4] Checking Ollama models..."
if command -v ollama &> /dev/null; then
    ollama pull nomic-embed-text || true
    ollama pull qwen2.5:1.5b || true
else
    echo "[WARNING] Ollama not found. Install from https://ollama.com"
fi

echo "[4/4] Launching GyanSutr..."
./venv/bin/python run_app.py