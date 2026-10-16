"""
Victoria - Screen Brightness Control Tool
Uses brightnessctl or xrandr to control screen brightness.
"""

import subprocess


def set_brightness(level: str) -> str:
    """
    Set screen brightness.
    
    Args:
        level: Brightness level - '50' for 50%, '+10' to increase, '-10' to decrease
    """
    level = level.strip()

    try:
        if level.startswith("+") or level.startswith("-"):
            # Relative adjustment with brightnessctl
            change = int(level)
            sign = "+" if change > 0 else "-"
            result = subprocess.run(
                ["brightnessctl", "set", f"{abs(change)}%{sign}"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return f"💡 Brightness adjusted: {level}%"
        else:
            # Absolute level
            val = max(1, min(100, int(level)))
            result = subprocess.run(
                ["brightnessctl", "set", f"{val}%"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return f"💡 Brightness set to: {val}%"

    except FileNotFoundError:
        # Fallback to xrandr
        try:
            # Get display name
            result = subprocess.run(
                ["xrandr", "--query"],
                capture_output=True, text=True, timeout=5,
            )
            display = None
            for line in result.stdout.split("\n"):
                if " connected" in line:
                    display = line.split()[0]
                    break

            if display:
                val = max(0.1, min(1.0, int(level.lstrip("+-")) / 100))
                subprocess.run(
                    ["xrandr", "--output", display, "--brightness", str(val)],
                    timeout=5,
                )
                return f"💡 Brightness set to: {int(val * 100)}% (via xrandr)"
            else:
                return "❌ No display found"
        except Exception as e:
            return f"❌ Brightness control error: {str(e)}"

    except Exception as e:
        return f"❌ Brightness control error: {str(e)}"

    return "❌ Failed to set brightness. Install brightnessctl: sudo apt install brightnessctl"


def get_brightness() -> str:
    """Get the current screen brightness level."""
    try:
        result = subprocess.run(
            ["brightnessctl", "info"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            import re
            match = re.search(r'\((\d+)%\)', result.stdout)
            if match:
                return f"💡 Brightness: {match.group(1)}%"
            return f"💡 Brightness info: {result.stdout.strip()}"

    except FileNotFoundError:
        pass

    return "❌ Cannot determine brightness. Install brightnessctl."
