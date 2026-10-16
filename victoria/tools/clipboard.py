"""
Victoria - Clipboard Tool
Manage system clipboard for both X11 (xclip/xsel) and Wayland (wl-clipboard).
"""

import os
import subprocess
import shutil


def _is_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY")) or os.environ.get("XDG_SESSION_TYPE") == "wayland"


def get_clipboard() -> str:
    """
    Get current clipboard contents.

    Returns:
        String containing the text in the clipboard.
    """
    wayland = _is_wayland()

    # Try Wayland first if in Wayland session
    if wayland and shutil.which("wl-paste"):
        try:
            res = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                return res.stdout
        except Exception:
            pass

    # Try xclip (works under X11 or XWayland)
    if shutil.which("xclip"):
        try:
            res = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode == 0:
                return res.stdout
        except Exception:
            pass

    # Try xsel
    if shutil.which("xsel"):
        try:
            res = subprocess.run(["xsel", "--clipboard", "--output"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                return res.stdout
        except Exception:
            pass

    # Fallback to wl-paste even if wayland env var wasn't detected
    if shutil.which("wl-paste"):
        try:
            res = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                return res.stdout
        except Exception:
            pass

    return "Clipboard utility not found. Please install xclip or wl-clipboard (wl-paste)."


def set_clipboard(text: str) -> str:
    """
    Copy text to clipboard.

    Args:
        text: Text to copy

    Returns:
        Status message.
    """
    wayland = _is_wayland()

    # Try Wayland first
    if wayland and shutil.which("wl-copy"):
        try:
            res = subprocess.run(["wl-copy"], input=text, text=True, timeout=3)
            if res.returncode == 0:
                return f"✅ Copied to clipboard ({len(text)} characters)."
        except Exception:
            pass

    # Try xclip
    if shutil.which("xclip"):
        try:
            res = subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text,
                text=True,
                timeout=3,
            )
            if res.returncode == 0:
                return f"✅ Copied to clipboard ({len(text)} characters)."
        except Exception:
            pass

    # Try xsel
    if shutil.which("xsel"):
        try:
            res = subprocess.run(
                ["xsel", "--clipboard", "--input"],
                input=text,
                text=True,
                timeout=3,
            )
            if res.returncode == 0:
                return f"✅ Copied to clipboard ({len(text)} characters)."
        except Exception:
            pass

    # Fallback wl-copy
    if shutil.which("wl-copy"):
        try:
            res = subprocess.run(["wl-copy"], input=text, text=True, timeout=3)
            if res.returncode == 0:
                return f"✅ Copied to clipboard ({len(text)} characters)."
        except Exception:
            pass

    return "Clipboard utility not found. Please install xclip or wl-clipboard."
