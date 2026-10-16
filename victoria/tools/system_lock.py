"""
Victoria - Voice Biometric System Lock & Unlock Engine
Enables Hariom to securely lock and unlock the Linux desktop screen using neural voice biometrics.
Uses GNOME ScreenSaver DBus & systemd-logind session management.
"""

import subprocess
from typing import Dict, Any, Optional
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


def unlock_system_by_voice(required_threshold: Optional[float] = None) -> Dict[str, Any]:
    """
    Unlock the desktop screen through REAL, live voice biometric verification.

    Security: this function captures a fresh audio sample and verifies it against
    the enrolled owner profile itself. No caller-supplied similarity score is
    accepted anymore (the previous API allowed trivially bypassing the check by
    passing similarity=0.88).

    Args:
        required_threshold: Optional override for the minimum biometric score
            (default: config voice.speaker_verify.unlock_threshold, else 0.60).

    Returns:
        Dict containing success (bool), similarity (float), and message (str)
    """
    from victoria.config import get_config
    from victoria.voice.speaker_verify import SpeakerVerifier

    cfg = get_config()
    if required_threshold is None:
        required_threshold = float(cfg.get("voice.speaker_verify.unlock_threshold", 0.60))

    verifier = SpeakerVerifier()

    # 1. Fail closed: an enrolled owner voiceprint is mandatory for voice unlock.
    if not verifier.is_enrolled():
        console.print("[bold red]🚫 Unlock Denied: no enrolled owner voiceprint.[/bold red]")
        return {
            "success": False,
            "similarity": 0.0,
            "message": "सुरक्षा: कोई वॉयसप्रिंट enrolled नहीं है, इसलिए voice unlock उपलब्ध नहीं है। कृपया पहले voice enrollment करें।"
        }

    # 2. Capture a fresh live sample from the owner.
    listener = None
    audio = None
    try:
        from victoria.voice.listener import AudioListener
        listener = AudioListener()
        audio = listener.record_until_silence()
    except Exception as e:
        console.print(f"[yellow]Voice capture failed during unlock: {e}[/yellow]")

    min_samples = int(getattr(listener, "sample_rate", 16000) * 1.0)
    if audio is None or len(audio) < min_samples:
        return {
            "success": False,
            "similarity": 0.0,
            "message": "सुरक्षा: अनलॉक के लिए कम से कम एक सेकंड की स्पष्ट आवाज़ चाहिए। कृपया फिर से बोलें।"
        }

    # 3. Strict biometric verification (no fail-open on short audio / missing encoder).
    is_owner, similarity = verifier.verify(audio, threshold=required_threshold, strict=True)
    if not is_owner:
        console.print(f"[bold red]🚫 Unlock Denied: Speaker similarity {similarity:.2f} < {required_threshold}[/bold red]")
        return {
            "success": False,
            "similarity": similarity,
            "message": f"सुरक्षा चेतावनी: आवाज़ हरिओम जी के बायोमेट्रिक वॉयसप्रिंट से मैच नहीं हुई (स्कोर: {similarity:.2f})। सिस्टम लॉक रहेगा।"
        }

    # Voice biometric verified! Proceed to dismiss lock screen
    console.print(f"[bold green]🔓 Voice Biometric Verified (match: {similarity:.2f} >= {required_threshold})! Unlocking desktop...[/bold green]")

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
    except Exception as e:
        console.print(f"[yellow]Unlock warning: {e}[/yellow]")

    # Double check lock status; retry once, then report the REAL state.
    if is_system_locked():
        # Wake up screen and try again
        try:
            subprocess.run(["loginctl", "unlock-sessions"], capture_output=True, timeout=2)
            subprocess.run(
                ["busctl", "--user", "call", "org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver", "SetActive", "b", "false"],
                capture_output=True, timeout=2
            )
        except Exception:
            pass

    if is_system_locked():
        return {
            "success": False,
            "similarity": similarity,
            "message": "आवाज़ सत्यापित हुई, लेकिन स्क्रीन लॉक नहीं खुल पाई। कृपया मैन्युअली अनलॉक करें।"
        }

    return {
        "success": True,
        "similarity": similarity,
        "message": f"जी हरिओम! आपकी आवाज़ सत्यापित हो गई है (बायोमेट्रिक मैच: {similarity:.2f})। सिस्टम स्क्रीन अनलॉक कर दी गई है।"
    }
