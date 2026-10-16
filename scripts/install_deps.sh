#!/bin/bash
# ============================================================
# Victoria - System Dependencies Installer for Linux
# Run this FIRST before pip install -r requirements.txt
# ============================================================

set -e

echo "╔══════════════════════════════════════════════╗"
echo "║   🤖 Victoria - System Dependencies Setup    ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Detect package manager
if command -v apt &> /dev/null; then
    PM="apt"
    INSTALL="sudo apt install -y"
elif command -v dnf &> /dev/null; then
    PM="dnf"
    INSTALL="sudo dnf install -y"
elif command -v pacman &> /dev/null; then
    PM="pacman"
    INSTALL="sudo pacman -S --noconfirm"
else
    echo "❌ Unsupported package manager. Install dependencies manually."
    exit 1
fi

echo "📦 Detected package manager: $PM"
echo ""

# --- Audio (PortAudio for microphone access) ---
echo "🎤 Installing audio dependencies..."
if [ "$PM" = "apt" ]; then
    $INSTALL portaudio19-dev python3-pyaudio libsndfile1 pulseaudio-utils alsa-utils
elif [ "$PM" = "dnf" ]; then
    $INSTALL portaudio-devel python3-pyaudio libsndfile pulseaudio-utils alsa-utils
elif [ "$PM" = "pacman" ]; then
    $INSTALL portaudio python-pyaudio libsndfile pulseaudio-utils alsa-utils
fi

# --- System control tools ---
echo "🖥️  Installing system control tools..."
if [ "$PM" = "apt" ]; then
    $INSTALL xdotool xclip wmctrl playerctl brightnessctl scrot xprop
elif [ "$PM" = "dnf" ]; then
    $INSTALL xdotool xclip wmctrl playerctl brightnessctl scrot xprop
elif [ "$PM" = "pacman" ]; then
    $INSTALL xdotool xclip wmctrl playerctl brightnessctl scrot xorg-xprop
fi

# --- D-Bus for notifications ---
echo "🔔 Installing D-Bus development files..."
if [ "$PM" = "apt" ]; then
    $INSTALL libdbus-1-dev libdbus-glib-1-dev pkg-config libgirepository1.0-dev
elif [ "$PM" = "dnf" ]; then
    $INSTALL dbus-devel dbus-glib-devel pkgconf gobject-introspection-devel
elif [ "$PM" = "pacman" ]; then
    $INSTALL dbus dbus-glib pkgconf gobject-introspection
fi

# --- Espeak (for Piper TTS fallback) ---
echo "🗣️  Installing espeak-ng (TTS fallback)..."
if [ "$PM" = "apt" ]; then
    $INSTALL espeak-ng
elif [ "$PM" = "dnf" ]; then
    $INSTALL espeak-ng
elif [ "$PM" = "pacman" ]; then
    $INSTALL espeak-ng
fi

# --- FFmpeg (for audio processing) ---
echo "🎬 Installing FFmpeg..."
if [ "$PM" = "apt" ]; then
    $INSTALL ffmpeg
elif [ "$PM" = "dnf" ]; then
    $INSTALL ffmpeg
elif [ "$PM" = "pacman" ]; then
    $INSTALL ffmpeg
fi

# --- AT-SPI for accessibility tree (Phase 2: Desktop REA) ---
echo "♿ Installing AT-SPI (for desktop app inspection)..."
if [ "$PM" = "apt" ]; then
    $INSTALL at-spi2-core python3-gi gir1.2-atspi-2.0
elif [ "$PM" = "dnf" ]; then
    $INSTALL at-spi2-core python3-gobject
elif [ "$PM" = "pacman" ]; then
    $INSTALL at-spi2-core python-gobject
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   ✅ System dependencies installed!           ║"
echo "║                                              ║"
echo "║   Next steps:                                ║"
echo "║   1. python -m venv .venv                    ║"
echo "║   2. source .venv/bin/activate               ║"
echo "║   3. pip install -r requirements.txt         ║"
echo "║   4. cp config/victoria.yaml.example \\       ║"
echo "║         config/victoria.yaml                 ║"
echo "║   5. python scripts/enroll_voice.py          ║"
echo "║   6. python -m victoria.main                 ║"
echo "╚══════════════════════════════════════════════╝"
