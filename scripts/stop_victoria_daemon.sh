#!/bin/bash
# ============================================================
# Project Victoria - Stop Daemon Script
# Gracefully stops Victoria background process
# ============================================================

echo "Stopping Victoria Assistant daemon..."

# Stop systemd service if running
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user stop victoria.service 2>/dev/null
fi

# Kill any remaining background python victoria processes
pkill -f "victoria --mode voice" 2>/dev/null
pkill -f "start_victoria_daemon.sh" 2>/dev/null

echo "✅ Victoria stopped."
