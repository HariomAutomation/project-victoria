#!/bin/bash
# ============================================================
# Project Victoria - Background Voice Daemon Launcher
# Starts Victoria in always-on voice mode with full system access
# ============================================================

PROJECT_DIR="/run/media/hariom/DATA_SAFE/PROJECT VICTORIA"
cd "$PROJECT_DIR" || exit 1

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/data/logs"
LOG_FILE="$PROJECT_DIR/data/logs/victoria_daemon.log"

# Setup environment variables for Audio & Display
export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export PULSE_SERVER="${PULSE_SERVER:-unix:/run/user/$(id -u)/pulse/native}"
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
export PYTHONUNBUFFERED=1

# Ensure microphone capture volume is at optimal sensitivity (65% avoids fan/room noise amplification)
amixer set Capture 65% unmute >/dev/null 2>&1 || true

echo "=================================================" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Victoria Background Voice Daemon..." >> "$LOG_FILE"

# Use .venv python if available, else system python3
if [ -f "$PROJECT_DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$PROJECT_DIR/.venv/bin/python3"
else
    PYTHON_BIN="$(which python3)"
fi

# Run Victoria in Voice Mode
exec "$PYTHON_BIN" -m victoria --mode voice >> "$LOG_FILE" 2>&1
