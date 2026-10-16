"""
Victoria - Non-Visual Desktop State & Screen Inspector
Inspects active GUI applications, media playback, workspace files,
and system status WITHOUT taking screenshots or writing images to disk.
"""

import os
import subprocess
import time
from typing import Dict, Any, List
from rich.console import Console

console = Console()

# Mapping of known GUI process names to friendly display names
GUI_APPS_MAP = {
    "antigravity-ide": "Antigravity IDE",
    "cursor": "Cursor IDE",
    "code": "VS Code",
    "chrome": "Google Chrome",
    "google-chrome": "Google Chrome",
    "firefox": "Firefox Browser",
    "gnome-terminal": "Terminal",
    "ptyxis": "Terminal",
    "nautilus": "Files (Nautilus)",
    "vlc": "VLC Media Player",
    "spotify": "Spotify",
    "discord": "Discord",
    "telegram-desktop": "Telegram",
    "slack": "Slack",
    "obs": "OBS Studio",
    "gedit": "Text Editor",
    "evince": "Document Viewer (PDF)",
    "libreoffice": "LibreOffice",
}


def get_running_gui_apps() -> List[str]:
    """Detect active GUI desktop applications running under the user session."""
    active_apps = []
    seen = set()

    for proc_name, display_name in GUI_APPS_MAP.items():
        if display_name in seen:
            continue
        try:
            res = subprocess.run(
                ["pgrep", "-u", "hariom", "-x", proc_name],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if res.returncode == 0 and res.stdout.strip():
                active_apps.append(display_name)
                seen.add(display_name)
        except Exception:
            pass

    return active_apps


def get_active_media_mpris() -> Dict[str, Any]:
    """Query MPRIS DBus to see what media/video/music is currently playing in browser or player."""
    media_info = {"playing": False, "title": "", "player": ""}
    try:
        res = subprocess.run(
            ["busctl", "--user", "list"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode != 0:
            return media_info

        mpris_services = [
            line.split()[0]
            for line in res.stdout.splitlines()
            if "org.mpris.MediaPlayer2" in line
        ]

        for srv in mpris_services:
            try:
                # Check status
                status_res = subprocess.run(
                    [
                        "busctl", "--user", "get-property",
                        srv, "/org/mpris/MediaPlayer2",
                        "org.mpris.MediaPlayer2.Player", "PlaybackStatus"
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                status = status_res.stdout.strip().replace('s "', '').replace('"', '')

                # Check metadata title
                meta_res = subprocess.run(
                    [
                        "busctl", "--user", "get-property",
                        srv, "/org/mpris/MediaPlayer2",
                        "org.mpris.MediaPlayer2.Player", "Metadata"
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                meta_out = meta_res.stdout

                title = ""
                if "xesam:title" in meta_out:
                    parts = meta_out.split('xesam:title" s "')
                    if len(parts) > 1:
                        title = parts[1].split('"')[0]

                player_name = srv.split(".")[-1].capitalize()
                if "chromium" in srv.lower() or "chrome" in srv.lower():
                    player_name = "Chrome"

                if status in ["Playing", "Paused"] or title:
                    media_info = {
                        "playing": status == "Playing",
                        "status": status,
                        "title": title or "Media",
                        "player": player_name,
                    }
                    break
            except Exception:
                continue
    except Exception:
        pass

    return media_info


def get_active_workspace_context() -> Dict[str, Any]:
    """Get context about active code projects, recent files, and terminal work."""
    from victoria.config import PROJECT_ROOT
    ws_name = os.path.basename(PROJECT_ROOT)

    # Check git branch if available
    branch = ""
    try:
        b_res = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if b_res.returncode == 0:
            branch = b_res.stdout.strip()
    except Exception:
        pass

    return {
        "project": ws_name,
        "path": str(PROJECT_ROOT),
        "git_branch": branch,
    }


def get_desktop_screen_overview() -> str:
    """
    Generate an instant, non-visual, zero-screenshot overview of what is happening
    on Hariom's desktop screen. No files are written to disk.
    """
    apps = get_running_gui_apps()
    media = get_active_media_mpris()
    ws = get_active_workspace_context()

    parts = []

    # 1. Apps
    if apps:
        apps_str = ", ".join(apps)
        parts.append(f"सक्रिय ऍप्लिकेशन्स: {apps_str}")
    else:
        parts.append("डेस्कटॉप शांत है")

    # 2. Project
    if ws.get("project"):
        proj_str = ws["project"]
        if ws.get("git_branch"):
            proj_str += f" (ब्रांच: {ws['git_branch']})"
        parts.append(f"प्रोजेक्ट: {proj_str}")

    # 3. Media
    if media.get("title") and media.get("playing"):
        parts.append(f"मीडिया: {media['player']} पर '{media['title']}' चल रहा है")
    elif media.get("title"):
        parts.append(f"मीडिया: {media['player']} पर '{media['title']}' पॉज़ है")

    # Natural concise speech summary for Hariom
    speech = f"हरिओम जी, आपकी स्क्रीन पर अभी {', '.join(apps) if apps else 'डेस्कटॉप'} खुला है"
    if "Antigravity IDE" in apps or "Cursor IDE" in apps or "VS Code" in apps:
        speech += f", जिसमें प्रोजेक्ट '{ws.get('project', 'Victoria')}' पर काम चल रहा है।"
    elif "Google Chrome" in apps:
        speech += " और ब्राउज़र खुला है।"
    else:
        speech += "।"

    if media.get("playing") and media.get("title"):
        speech += f" बैकग्राउंड में {media['player']} पर '{media['title']}' चल रहा है।"

    return speech
