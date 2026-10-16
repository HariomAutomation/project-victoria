"""
Project Victoria - GUI / HUD Package (Phase 4)
Provides a sci-fi, cyberpunk, dark glassmorphic 3D HUD & Control Deck:
- Three.js 3D Neural Particle Core / Hologram
- Real-time Audio Waveform & Speech Visualizer
- REA (Reverse Engineer Anything) Command Deck
- Live System Telemetry (CPU, RAM, Disk, Audio Volume)
- Interactive Hindi/English Voice & Chat Console
"""

def __getattr__(name: str):
    if name == "start_hud_server":
        from victoria.hud.server import start_hud_server
        return start_hud_server
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["start_hud_server"]
