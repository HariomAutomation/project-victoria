"""
Victoria - App Launcher Tool
Open, close, and manage applications on Linux.
"""

import subprocess
import shlex


# Common app name to binary mapping
APP_ALIASES = {
    "browser": "xdg-open http://",
    "firefox": "firefox",
    "chrome": "google-chrome-stable",
    "chromium": "chromium",
    "terminal": "x-terminal-emulator",
    "file manager": "nautilus",
    "nautilus": "nautilus",
    "files": "nautilus",
    "thunar": "thunar",
    "dolphin": "dolphin",
    "text editor": "gedit",
    "gedit": "gedit",
    "code": "code",
    "vscode": "code",
    "vs code": "code",
    "calculator": "gnome-calculator",
    "calc": "gnome-calculator",
    "settings": "gnome-control-center",
    "system monitor": "gnome-system-monitor",
    "screenshot": "gnome-screenshot",
    "vlc": "vlc",
    "gimp": "gimp",
    "libreoffice": "libreoffice",
    "spotify": "spotify",
    "discord": "discord",
    "telegram": "telegram-desktop",
    "obs": "obs",
    "blender": "blender",
    "inkscape": "inkscape",
}


def open_application(app_name: str) -> str:
    """
    Open an application by name.
    Tries the name directly first, then checks common aliases.
    """
    app_lower = app_name.lower().strip()

    # Check aliases
    binary = APP_ALIASES.get(app_lower, app_lower)

    try:
        # Launch in background, detached from terminal
        subprocess.Popen(
            shlex.split(binary),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return f"✅ Opened: {app_name}"

    except FileNotFoundError:
        # Try with gtk-launch (for .desktop files)
        try:
            subprocess.Popen(
                ["gtk-launch", app_lower],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return f"✅ Opened: {app_name} (via gtk-launch)"
        except Exception:
            pass

        # Try xdg-open as last resort
        try:
            subprocess.Popen(
                ["xdg-open", app_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return f"✅ Opened: {app_name} (via xdg-open)"
        except Exception:
            return f"❌ Application not found: {app_name}. Try the exact binary name."

    except Exception as e:
        return f"❌ Error opening {app_name}: {str(e)}"


def close_application(app_name: str) -> str:
    """Close an application by name or window title."""
    app_lower = app_name.lower().strip()
    binary = APP_ALIASES.get(app_lower, app_lower)

    try:
        # Try wmctrl first (close window gracefully)
        result = subprocess.run(
            ["wmctrl", "-c", app_name],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return f"✅ Closed window: {app_name}"

    except FileNotFoundError:
        pass

    # Fallback: pkill
    try:
        result = subprocess.run(
            ["pkill", "-f", binary],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return f"✅ Killed: {app_name}"
        else:
            return f"⚠️ No process found matching: {app_name}"
    except Exception as e:
        return f"❌ Error closing {app_name}: {str(e)}"


def list_running_apps() -> str:
    """List all running GUI applications with window titles."""
    try:
        result = subprocess.run(
            ["wmctrl", "-l"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            apps = []
            for line in lines:
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    apps.append(parts[3])
            return "Running apps:\n" + "\n".join(f"  • {app}" for app in apps)
        else:
            # Fallback without wmctrl
            result = subprocess.run(
                ["xdotool", "search", "--name", ""],
                capture_output=True, text=True, timeout=5,
            )
            return "Install wmctrl for better app listing: sudo apt install wmctrl"

    except FileNotFoundError:
        # No wmctrl, use xdotool or just list processes
        result = subprocess.run(
            ["ps", "-eo", "comm", "--sort=-%mem"],
            capture_output=True, text=True, timeout=5,
        )
        processes = result.stdout.strip().split("\n")[1:16]  # Top 15
        return "Top processes:\n" + "\n".join(f"  • {p.strip()}" for p in processes)
