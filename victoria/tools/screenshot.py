"""
Victoria - Screenshot Tool
Take screenshots of full screen or specific windows.
"""

import subprocess
import os
import time


def take_screenshot(filename: str = None, window: str = None) -> str:
    """
    Take a screenshot.
    
    Args:
        filename: Output filename (default: screenshot_<timestamp>.png)
        window: Specific window name to capture (default: full screen)
    """
    if filename is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"

    # Ensure it's saved in Pictures or home
    if not os.path.isabs(filename):
        pictures_dir = os.path.expanduser("~/Pictures")
        os.makedirs(pictures_dir, exist_ok=True)
        filepath = os.path.join(pictures_dir, filename)
    else:
        filepath = filename

    try:
        if window:
            # Capture specific window
            # First, find the window ID
            result = subprocess.run(
                ["xdotool", "search", "--name", window],
                capture_output=True, text=True, timeout=5,
            )
            if result.stdout.strip():
                window_id = result.stdout.strip().split("\n")[0]
                subprocess.run(
                    ["import", "-window", window_id, filepath],
                    timeout=10,
                )
                return f"📸 Screenshot saved: {filepath} (window: {window})"

        # Full screen screenshot - try multiple tools
        tools = [
            ["scrot", filepath],
            ["gnome-screenshot", "-f", filepath],
            ["import", "-window", "root", filepath],
            ["grim", filepath],  # Wayland
        ]

        for cmd in tools:
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=10)
                if result.returncode == 0 and os.path.exists(filepath):
                    return f"📸 Screenshot saved: {filepath}"
            except FileNotFoundError:
                continue

        return "❌ No screenshot tool found. Install scrot: sudo apt install scrot"

    except Exception as e:
        return f"❌ Screenshot error: {str(e)}"
