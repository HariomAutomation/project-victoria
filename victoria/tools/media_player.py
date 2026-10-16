"""
Victoria - Media Player Control Tool
Control media playback (Spotify, VLC, browser media, MPV, etc.) using playerctl / MPRIS D-Bus.
"""

import subprocess
import shutil


def _has_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def media_control(action: str) -> str:
    """
    Control media playback across running media players.

    Args:
        action: One of 'play', 'pause', 'play-pause', 'next', 'previous', 'stop'

    Returns:
        Status message of the action.
    """
    action = action.lower().strip()
    valid_actions = {
        "play": "play",
        "pause": "pause",
        "play-pause": "play-pause",
        "play_pause": "play-pause",
        "toggle": "play-pause",
        "next": "next",
        "skip": "next",
        "previous": "previous",
        "prev": "previous",
        "stop": "stop",
    }

    if action not in valid_actions:
        return f"Unknown media action: '{action}'. Valid actions: play, pause, play-pause, next, previous, stop."

    cmd_action = valid_actions[action]

    if _has_command("playerctl"):
        try:
            res = subprocess.run(
                ["playerctl", cmd_action],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                return f"✅ Media command '{cmd_action}' sent successfully."
            elif "No players found" in res.stderr or not res.stderr.strip():
                return "ℹ️ No active media players found running."
            else:
                return f"Media control error: {res.stderr.strip()}"
        except Exception as e:
            return f"Failed to execute playerctl: {e}"

    # Fallback to DBus MPRIS via qdbus or dbus-send if playerctl is missing
    return "playerctl is not installed. Please install it (e.g. sudo apt install playerctl / sudo pacman -S playerctl)."


def get_now_playing() -> str:
    """
    Get track information currently playing on active media players.

    Returns:
        Formatted string containing Title, Artist, Album, and Player status.
    """
    if not _has_command("playerctl"):
        return "playerctl not installed. Cannot retrieve media status."

    try:
        status_res = subprocess.run(
            ["playerctl", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if status_res.returncode != 0:
            return "ℹ️ No media currently playing."

        status = status_res.stdout.strip()

        meta_res = subprocess.run(
            [
                "playerctl",
                "metadata",
                "--format",
                "Title: {{xesam:title}}\nArtist: {{xesam:artist}}\nAlbum: {{xesam:album}}\nPlayer: {{playerName}}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        metadata = meta_res.stdout.strip() if meta_res.returncode == 0 else ""

        if metadata:
            return f"🎵 Currently {status}:\n{metadata}"
        return f"🎵 Media Status: {status}"
    except Exception as e:
        return f"Error getting media status: {e}"
