"""
Project Victoria - GUI / HUD Package (Phase 4)
Provides a sci-fi, cyberpunk, dark glassmorphic 3D HUD & Control Deck:
- Three.js 3D Neural Particle Core / Hologram
- Real-time Audio Waveform & Speech Visualizer
- REA (Reverse Engineer Anything) Command Deck
- Live System Telemetry (CPU, RAM, Disk, Audio Volume)
- Interactive Hindi/English Voice & Chat Console
"""

from victoria.hud.server import start_hud_server

__all__ = ["start_hud_server"]
