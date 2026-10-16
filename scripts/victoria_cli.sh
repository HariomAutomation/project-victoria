#!/bin/bash
# ============================================================
# Victoria AI Assistant - Master System CLI Launcher
# Usage:
#   victoria                (interactive text mode)
#   victoria --mode voice   (continuous two-way voice mode)
#   victoria --mode hud     (3D holographic web deck on port 7860)
#   victoria --rea <target> (deep reverse engineer any app/url/db/device)
# ============================================================

PROJECT_DIR="/run/media/hariom/DATA_SAFE/PROJECT VICTORIA"
cd "$PROJECT_DIR" || exit 1

export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export PULSE_SERVER="${PULSE_SERVER:-unix:/run/user/$(id -u)/pulse/native}"
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
export PYTHONUNBUFFERED=1

# Ensure microphone capture volume is at optimal sensitivity (65%)
amixer set Capture 65% unmute >/dev/null 2>&1 || true

PYTHON_BIN="$PROJECT_DIR/.venv/bin/python3"

exec "$PYTHON_BIN" -m victoria "$@"
