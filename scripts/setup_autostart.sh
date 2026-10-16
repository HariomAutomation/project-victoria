#!/bin/bash
# ============================================================
# Project Victoria - Autostart & Background Daemon Setup
# Configures Victoria to start automatically on laptop boot/login
# ============================================================

# Dynamically resolve project directory
TARGET_FILE="${BASH_SOURCE[0]}"
while [ -L "$TARGET_FILE" ]; do
    TARGET_DIR="$(cd -P "$(dirname "$TARGET_FILE")" >/dev/null 2>&1 && pwd)"
    TARGET_FILE="$(readlink "$TARGET_FILE")"
    [[ $TARGET_FILE != /* ]] && TARGET_FILE="$TARGET_DIR/$TARGET_FILE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$TARGET_FILE")" >/dev/null 2>&1 && pwd)"
PROJECT_DIR="$(cd -P "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
DAEMON_SCRIPT="$PROJECT_DIR/scripts/start_victoria_daemon.sh"

echo "╔════════════════════════════════════════════════════════╗"
echo "║   🤖 Victoria - Laptop Autostart & Daemon Setup        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# 1. Setup XDG Autostart (.config/autostart)
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

cat << EOF > "$AUTOSTART_DIR/victoria.desktop"
[Desktop Entry]
Type=Application
Name=Project Victoria AI Assistant
Comment=Always-on Hindi/English Voice AI Assistant with REA Engine
Exec=/bin/bash "$DAEMON_SCRIPT"
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Terminal=false
Categories=Utility;Audio;
EOF

chmod +x "$AUTOSTART_DIR/victoria.desktop"
echo "✅ XDG Desktop Autostart configured: $AUTOSTART_DIR/victoria.desktop"

# 2. Setup Systemd User Service (~/.config/systemd/user)
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"

cat << EOF > "$SYSTEMD_USER_DIR/victoria.service"
[Unit]
Description=Victoria Personal AI Assistant Daemon (Always-On Voice & REA)
After=graphical-session.target sound.target pulseaudio.service pipewire.service
Wants=sound.target

[Service]
Type=simple
ExecStart=/bin/bash "$DAEMON_SCRIPT"
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

# Reload systemd and enable user service
if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload
    systemctl --user enable victoria.service
    loginctl enable-linger "$(whoami)" 2>/dev/null || true
    echo "✅ Systemd user service enabled & lingering active: victoria.service"
fi

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║   🎉 Setup Complete!                                  ║"
echo "║                                                        ║"
echo "║   Victoria will now start automatically whenever       ║"
echo "║   you power on or log into your laptop!                ║"
echo "║                                                        ║"
echo "║   Commands:                                            ║"
echo "║   • Start now:  systemctl --user start victoria        ║"
echo "║   • Stop:       systemctl --user stop victoria         ║"
echo "║   • Status:     systemctl --user status victoria       ║"
echo "║   • Live Logs:  tail -f '$PROJECT_DIR/data/logs/victoria_daemon.log' ║"
echo "╚════════════════════════════════════════════════════════╝"
