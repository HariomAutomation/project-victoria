"""
Victoria - Audio/Volume Control Tool
Control system volume using pactl (PulseAudio) or wpctl (PipeWire).
"""

import subprocess


def _get_audio_system() -> str:
    """Detect which audio system is in use."""
    try:
        result = subprocess.run(["wpctl", "status"], capture_output=True, timeout=3)
        if result.returncode == 0:
            return "pipewire"
    except FileNotFoundError:
        pass

    try:
        result = subprocess.run(["pactl", "info"], capture_output=True, timeout=3)
        if result.returncode == 0:
            return "pulseaudio"
    except FileNotFoundError:
        pass

    return "amixer"


def set_volume(level: str) -> str:
    """
    Set system volume.
    
    Args:
        level: Volume level - '50' for 50%, '+10' to increase, '-10' to decrease,
               'mute' to mute, 'unmute' to unmute
    """
    level = level.strip().lower()
    audio_sys = _get_audio_system()

    try:
        if level == "mute":
            if audio_sys == "pipewire":
                subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1"], timeout=5)
            elif audio_sys == "pulseaudio":
                subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"], timeout=5)
            else:
                subprocess.run(["amixer", "set", "Master", "mute"], timeout=5)
            return "🔇 Volume muted"

        elif level == "unmute":
            if audio_sys == "pipewire":
                subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"], timeout=5)
            elif audio_sys == "pulseaudio":
                subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], timeout=5)
            else:
                subprocess.run(["amixer", "set", "Master", "unmute"], timeout=5)
            return "🔊 Volume unmuted"

        elif level.startswith("+") or level.startswith("-"):
            # Relative adjustment
            if audio_sys == "pipewire":
                # wpctl uses decimal (0.1 = 10%)
                change = int(level) / 100
                subprocess.run(
                    ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{abs(change)}{'+' if change > 0 else '-'}"],
                    timeout=5,
                )
            elif audio_sys == "pulseaudio":
                subprocess.run(
                    ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"],
                    timeout=5,
                )
            else:
                subprocess.run(
                    ["amixer", "set", "Master", f"{abs(int(level))}%{'+' if int(level) > 0 else '-'}"],
                    timeout=5,
                )
            return f"🔊 Volume adjusted: {level}%"

        else:
            # Absolute level
            vol = int(level)
            vol = max(0, min(100, vol))

            if audio_sys == "pipewire":
                subprocess.run(
                    ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{vol/100:.2f}"],
                    timeout=5,
                )
            elif audio_sys == "pulseaudio":
                subprocess.run(
                    ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{vol}%"],
                    timeout=5,
                )
            else:
                subprocess.run(
                    ["amixer", "set", "Master", f"{vol}%"],
                    timeout=5,
                )
            return f"🔊 Volume set to: {vol}%"

    except Exception as e:
        return f"❌ Volume control error: {str(e)}"


def get_volume() -> str:
    """Get the current system volume level."""
    audio_sys = _get_audio_system()

    try:
        if audio_sys == "pipewire":
            result = subprocess.run(
                ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                # Output: "Volume: 0.50" or "Volume: 0.50 [MUTED]"
                output = result.stdout.strip()
                parts = output.split()
                if len(parts) >= 2:
                    vol = float(parts[1]) * 100
                    muted = "[MUTED]" in output
                    return f"🔊 Volume: {vol:.0f}%{' (muted)' if muted else ''}"

        elif audio_sys == "pulseaudio":
            result = subprocess.run(
                ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                # Parse percentage from output
                import re
                match = re.search(r'(\d+)%', result.stdout)
                if match:
                    vol = int(match.group(1))
                    return f"🔊 Volume: {vol}%"

        # Fallback: amixer
        result = subprocess.run(
            ["amixer", "get", "Master"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            import re
            match = re.search(r'\[(\d+)%\]', result.stdout)
            muted = "[off]" in result.stdout
            if match:
                return f"🔊 Volume: {match.group(1)}%{' (muted)' if muted else ''}"

        return "❌ Could not determine volume level"

    except Exception as e:
        return f"❌ Error getting volume: {str(e)}"
