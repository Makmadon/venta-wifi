#!/usr/bin/env bash
# ==============================================================================
# Script de Verificación de Hardware y Diagnóstico Wi-Fi (PC & Raspberry Pi)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -f "$PROJECT_ROOT/venv/bin/python" ]; then
  PYTHON="$PROJECT_ROOT/venv/bin/python"
else
  PYTHON="python3"
fi

$PYTHON -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from app.hardware_check import print_hardware_summary
print_hardware_summary()
"
