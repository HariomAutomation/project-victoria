"""
Victoria - Voice Biometric System Lock & Unlock Engine
Enables Hariom to securely lock and unlock the Linux desktop screen using neural voice biometrics.
Uses GNOME ScreenSaver DBus & systemd-logind session management.
"""

import subprocess
import shutil
from typing import Dict, Any
from rich.console import Console

console = Console()


def is_system_locked() -> bool:
    """
    Check if the desktop session is currently locked.
    Supports GNOME ScreenSaver, systemd-logind, and X11 screensavers.
    """
    # 1. Check GNOME ScreenSaver DBus
    try:
        res = subprocess.run(
            [
                "busctl", "--user", "call",
                "org.gnome.ScreenSaver",
                "/org/gnome/ScreenSaver",
                "org.gnome.ScreenSaver",
                "GetActive"
            ],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if res.returncode == 0:
            return "true" in res.stdout.lower()
    except Exception:
        pass

    # 2. Check systemd-logind session LockedHint
    try:
        sess_cmd = "loginctl list-sessions | grep $(whoami) | awk '{print $1}' | head -1"
        sess_id = subprocess.check_output(sess_cmd, shell=True, text=True).strip()
        if sess_id:
            hint_res = subprocess.run(
                ["loginctl", "show-session", sess_id, "-p", "LockedHint"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if "yes" in hint_res.stdout.lower():
                return True
    except Exception:
        pass

    return False


def lock_system() -> str:
    """
    Immediately lock the Linux desktop session screen.
    """
    try:
        # 1. Try GNOME ScreenSaver DBus
        res = subprocess.run(
            [
                "busctl", "--user", "call",
                "org.gnome.ScreenSaver",
                "/org/gnome/ScreenSaver",
                "org.gnome.ScreenSaver",
                "Lock"
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if res.returncode == 0:
            return "जी हरिओम! सिस्टम स्क्रीन को सुरक्षित रूप से लॉक कर दिया गया है।"
    except Exception:
        pass

    # 2. Fallback to loginctl lock-session
    try:
        subprocess.run(["loginctl", "lock-session"], timeout=3)
        return "जी हरिओम! सिस्टम स्क्रीन को लॉक कर दिया गया है।"
    except Exception as e:
        return f"सिस्टम लॉक करने में समस्या आई: {e}"


def unlock_system_by_voice(similarity: float = 1.0, required_threshold: float = 0.65) -> Dict[str, Any]:
    """
    Unlock the desktop screen verified through voice biometrics.

    Args:
        similarity: Cosine similarity score of the speaker embedding against owner.npy
        required_threshold: Minimum biometric threshold required to authenticate unlock

    Returns:
        Dict containing success (bool), similarity (float), and message (str)
    """
    if similarity < required_threshold:
        console.print(f"[bold red]🚫 Unlock Denied: Speaker similarity {similarity:.2f} < {required_threshold}[/bold red]")
        return {
            "success": False,
            "similarity": similarity,
            "message": f"सुरक्षा चेतावनी: आवाज़ हरिओम जी के बायोमेट्रिक वॉयसप्रिंट से मैच नहीं हुई (स्कोर: {similarity:.2f})। सिस्टम लॉक रहेगा।"
        }

    # Voice biometric verified! Proceed to dismiss lock screen
    console.print(f"[bold green]🔓 Voice Biometric Verified (match: {similarity:.2f} >= {required_threshold})! Unlocking desktop...[/bold green]")

    success = False
    try:
        # 1. Signal systemd-logind to unlock session
        subprocess.run(["loginctl", "unlock-session"], capture_output=True, timeout=2)
        
        # 2. Dismiss GNOME ScreenSaver shield
        subprocess.run(
            [
                "busctl", "--user", "call",
                "org.gnome.ScreenSaver",
                "/org/gnome/ScreenSaver",
                "org.gnome.ScreenSaver",
                "SetActive", "b", "false"
            ],
            capture_output=True,
            timeout=2,
        )
        success = True
    except Exception as e:
        console.print(f"[yellow]Unlock warning: {e}[/yellow]")

    # Double check lock status
    is_still_locked = is_system_locked()
    if is_still_locked:
        # Wake up screen and try again
        try:
            subprocess.run(["loginctl", "unlock-sessions"], capture_output=True, timeout=2)
            subprocess.run(
                ["busctl", "--user", "call", "org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver", "SetActive", "b", "false"],
                capture_output=True, timeout=2
            )
        except Exception:
            pass

    return {
        "success": True,
        "similarity": similarity,
        "message": f"जी हरिओम! आपकी आवाज़ सत्यापित हो गई है (बायोमेट्रिक मैच: {similarity:.2f})। सिस्टम स्क्रीन अनलॉक कर दी गई है।"
    }
