"""
Victoria - Media Player Control Tool
Control media playback (Spotify, VLC, browser media, MPV, etc.) using playerctl / MPRIS D-Bus.
"""

import subprocess
import shutil


import os

# Ensure ~/.local/bin is in PATH
if "/home/hariom/.local/bin" not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"/home/hariom/.local/bin:{os.environ.get('PATH', '')}"


def _has_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None or os.path.exists(f"/home/hariom/.local/bin/{cmd}")


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

    # 1. Try playerctl
    playerctl_bin = shutil.which("playerctl") or "/home/hariom/.local/bin/playerctl"
    if os.path.exists(playerctl_bin):
        try:
            res = subprocess.run(
                [playerctl_bin, cmd_action],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                return f"✅ Media command '{cmd_action}' sent successfully."
            elif "No players found" not in res.stderr:
                return f"✅ Media command '{cmd_action}' executed."
        except Exception:
            pass

    # 2. Native DBus MPRIS fallback via dbus-send / busctl
    mpris_method_map = {
        "play": "Play",
        "pause": "Pause",
        "play-pause": "PlayPause",
        "next": "Next",
        "previous": "Previous",
        "stop": "Stop",
    }
    mpris_method = mpris_method_map.get(cmd_action, "PlayPause")

    try:
        bus_res = subprocess.run(["busctl", "--user", "list"], capture_output=True, text=True, timeout=2)
        if bus_res.returncode == 0:
            players = [
                line.split()[0]
                for line in bus_res.stdout.splitlines()
                if "org.mpris.MediaPlayer2" in line
            ]
            controlled = []
            for srv in players:
                # Try dbus-send for compatibility with snap (e.g. Spotify)
                cmd = [
                    "dbus-send", "--session", "--type=method_call",
                    f"--dest={srv}", "/org/mpris/MediaPlayer2",
                    f"org.mpris.MediaPlayer2.Player.{mpris_method}"
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                if r.returncode == 0:
                    controlled.append(srv.split(".")[-1].capitalize())

            if controlled:
                return f"✅ Media '{cmd_action}' sent to: {', '.join(controlled)}"
    except Exception as e:
        return f"Media control error: {e}"

    return "ℹ️ No active media players found running."


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
