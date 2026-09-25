#!/usr/bin/env bash
# ==============================================================================
# Portal Launcher Script (Runs as unprivileged user on port 8000)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Determine python executable
if [ -f "$PROJECT_ROOT/venv/bin/python" ]; then
  PYTHON="$PROJECT_ROOT/venv/bin/python"
  UVICORN="$PROJECT_ROOT/venv/bin/uvicorn"
else
  PYTHON="python3"
  UVICORN="uvicorn"
fi

echo "=========================================================="
echo " Starting Local Ticketing & Captive Portal Backend"
echo " Python: $($PYTHON --version)"
echo " Root  : $PROJECT_ROOT"
echo "=========================================================="

# Auto-seed database if empty
$PYTHON "$PROJECT_ROOT/scripts/seed_data.py"

# Hardware and Wi-Fi capability check
$PYTHON -c "from app.hardware_check import print_hardware_summary; print_hardware_summary()"

# Start FastAPI server on port 8000
echo "Launching FastAPI on 0.0.0.0:8000..."
exec $UVICORN main:app --host 0.0.0.0 --port 8000 --log-level info
