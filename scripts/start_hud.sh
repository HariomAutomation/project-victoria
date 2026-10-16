#!/bin/bash
# ============================================================
# Project Victoria - 3D Holographic HUD Web Launcher
# Launches the interactive web dashboard on http://localhost:7860
# ============================================================

PROJECT_DIR="/run/media/hariom/DATA_SAFE/PROJECT VICTORIA"
cd "$PROJECT_DIR" || exit 1

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export PULSE_SERVER="${PULSE_SERVER:-unix:/run/user/$(id -u)/pulse/native}"
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
export PYTHONUNBUFFERED=1

PORT="${1:-7860}"

if [ -f "$PROJECT_DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$PROJECT_DIR/.venv/bin/python3"
else
    PYTHON_BIN="$(which python3)"
fi

echo "============================================================"
echo "⚡ Starting Victoria 3D Holographic HUD & REA Control Deck"
echo "🌐 URL: http://localhost:$PORT"
echo "============================================================"

exec "$PYTHON_BIN" -m victoria --mode hud --port "$PORT"
