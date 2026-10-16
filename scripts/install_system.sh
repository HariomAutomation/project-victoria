#!/bin/bash
# ============================================================
# Project Victoria - Complete System Installer
# Installs Victoria globally on Ubuntu Linux:
#   1. Global CLI launcher: ~/.local/bin/victoria
#   2. GNOME Desktop Launcher: ~/.local/share/applications/victoria.desktop
#   3. Systemd User Background Service (Autostart on boot)
#   4. Terminal alias in ~/.bashrc
# ============================================================

set -e

# Dynamically resolve project directory
TARGET_FILE="${BASH_SOURCE[0]}"
while [ -L "$TARGET_FILE" ]; do
    TARGET_DIR="$(cd -P "$(dirname "$TARGET_FILE")" >/dev/null 2>&1 && pwd)"
    TARGET_FILE="$(readlink "$TARGET_FILE")"
    [[ $TARGET_FILE != /* ]] && TARGET_FILE="$TARGET_DIR/$TARGET_FILE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$TARGET_FILE")" >/dev/null 2>&1 && pwd)"
PROJECT_DIR="$(cd -P "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
cd "$PROJECT_DIR"

echo "============================================================"
echo "⚡ Installing Project Victoria on Ubuntu Linux..."
echo "📂 Project Root: $PROJECT_DIR"
echo "============================================================"

# 1. Create directories
mkdir -p "$HOME/.local/bin"
mkdir -p "$HOME/.local/share/applications"
mkdir -p "$HOME/.config/autostart"

# 2. Install global CLI executable
chmod +x "$PROJECT_DIR/scripts/victoria_cli.sh"
ln -sf "$PROJECT_DIR/scripts/victoria_cli.sh" "$HOME/.local/bin/victoria"
echo "✅ Global CLI installed: $HOME/.local/bin/victoria"

cat << 'EOF' > "$HOME/.local/bin/victoria-enroll"
#!/bin/bash
exec "$HOME/.local/bin/victoria" --enroll "$@"
EOF
chmod +x "$HOME/.local/bin/victoria-enroll"

cat << 'EOF' > "$HOME/.local/bin/victoria-test"
#!/bin/bash
exec "$HOME/.local/bin/victoria" --test-voice "$@"
EOF
chmod +x "$HOME/.local/bin/victoria-test"

cat << 'EOF' > "$HOME/.local/bin/victoria-hud"
#!/bin/bash
exec "$HOME/.local/bin/victoria" --mode hud "$@"
EOF
chmod +x "$HOME/.local/bin/victoria-hud"
echo "✅ Helper CLIs installed: victoria-enroll, victoria-test, victoria-hud"

# 3. Install Desktop Application Launcher with Holographic Icon
sed -e "s|{{PROJECT_DIR}}|$PROJECT_DIR|g" \
    -e "s|{{HOME}}|$HOME|g" \
    "$PROJECT_DIR/scripts/victoria.desktop" > "$HOME/.local/share/applications/victoria.desktop"
chmod +x "$HOME/.local/share/applications/victoria.desktop"
update-desktop-database "$HOME/.local/share/applications/" 2>/dev/null || true
echo "✅ Desktop Application installed in GNOME Dash / App Launcher"

# 4. Install Background Autostart
"$PROJECT_DIR/scripts/setup_autostart.sh"

# 5. Add to ~/.bashrc if not present
if ! grep -q 'victoria-enroll' "$HOME/.bashrc" 2>/dev/null; then
    cat << 'EOF' >> "$HOME/.bashrc"

# Project Victoria AI Assistant
export PATH="$HOME/.local/bin:$PATH"
alias victoria='$HOME/.local/bin/victoria'
alias victoria-enroll='$HOME/.local/bin/victoria-enroll'
alias victoria-test='$HOME/.local/bin/victoria-test'
EOF
    echo "✅ Aliases & PATH added to ~/.bashrc"
fi

echo "============================================================"
echo "🎉 Victoria Installation Complete!"
echo "• Run anywhere in terminal: 'victoria'"
echo "• Or search 'Victoria AI Assistant' in Ubuntu App Grid"
echo "• Background Daemon status: systemctl --user status victoria"
echo "============================================================"
