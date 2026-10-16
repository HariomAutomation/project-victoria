#!/bin/bash
# ============================================================
# Victoria AI Assistant - Desktop Holographic App Launcher
# ============================================================

PROJECT_DIR="/run/media/hariom/DATA_SAFE/PROJECT VICTORIA"
cd "$PROJECT_DIR" || exit 1

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export PULSE_SERVER="${PULSE_SERVER:-unix:/run/user/$(id -u)/pulse/native}"
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# Set optimal microphone sensitivity
amixer set Capture 65% unmute >/dev/null 2>&1 || true

# Execute victoria in HUD mode
exec "$PROJECT_DIR/.venv/bin/python3" -m victoria --mode hud
