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

        # 1. Native Wayland / GNOME Desktop Portal (100% full-color screenshot on Ubuntu Wayland)
        try:
            import dbus, dbus.mainloop.glib
            import shutil
            from gi.repository import GLib

            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            bus = dbus.SessionBus()
            portal = bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop")
            iface = dbus.Interface(portal, "org.freedesktop.portal.Screenshot")
            loop = GLib.MainLoop()

            result_path = [None]
            def _on_portal_response(response_code, results):
                if response_code == 0 and "uri" in results:
                    uri = str(results["uri"])
                    if uri.startswith("file://"):
                        result_path[0] = uri[7:]
                loop.quit()

            req_path = iface.Screenshot("", {"interactive": dbus.Boolean(False)})
            req_obj = bus.get_object("org.freedesktop.portal.Desktop", req_path)
            req_iface = dbus.Interface(req_obj, "org.freedesktop.portal.Request")
            req_iface.connect_to_signal("Response", _on_portal_response)

            GLib.timeout_add_seconds(3, loop.quit)
            loop.run()

            if result_path[0] and os.path.exists(result_path[0]):
                shutil.copy2(result_path[0], filepath)
                return f"📸 Screenshot saved: {filepath}"
        except Exception:
            pass

        # Full screen screenshot - fallback to CLI tools
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

        return "❌ No screenshot tool found."

    except Exception as e:
        return f"❌ Screenshot error: {str(e)}"
