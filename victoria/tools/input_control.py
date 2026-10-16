"""
Victoria - Mouse & Keyboard System Automation Controller
Full GUI automation: mouse movement, clicks, drags, scrolling, typing, and hotkeys.
Works natively on Linux via X11 / XWayland using Xlib XTEST protocol.
"""

import os
import glob
import time
from typing import Dict, Any, List, Optional, Union
from rich.console import Console

console = Console()


def _ensure_xauthority():
    """Ensure XAUTHORITY is set correctly for XWayland / X11."""
    if "XAUTHORITY" not in os.environ or not os.path.exists(os.environ["XAUTHORITY"]):
        uid = os.getuid()
        candidates = glob.glob(f"/run/user/{uid}/.mutter-Xwaylandauth.*") + [
            f"/home/{os.environ.get('USER', 'hariom')}/.Xauthority",
            f"/run/user/{uid}/gdm/Xauthority",
        ]
        for c in candidates:
            if os.path.exists(c):
                os.environ["XAUTHORITY"] = c
                break

    if "DISPLAY" not in os.environ:
        os.environ["DISPLAY"] = ":0"


class InputController:
    """
    Low-level Mouse & Keyboard Automation Controller using Python Xlib.
    """

    def __init__(self):
        _ensure_xauthority()
        import Xlib.display
        import Xlib.X
        import Xlib.XK
        import Xlib.ext.xtest as xtest

        self.display = Xlib.display.Display()
        self.screen = self.display.screen()
        self.root = self.screen.root
        self.X = Xlib.X
        self.XK = Xlib.XK
        self.xtest = xtest

    def get_screen_size(self) -> tuple[int, int]:
        """Get total screen resolution (width, height)."""
        return self.screen.width_in_pixels, self.screen.height_in_pixels

    def get_pointer_position(self) -> tuple[int, int]:
        """Get current mouse (x, y) coordinates."""
        query = self.root.query_pointer()
        return query.root_x, query.root_y

    def move_mouse(self, x: int, y: int, smooth: bool = False):
        """Move mouse cursor to coordinates (x, y)."""
        w, h = self.get_screen_size()
        target_x = max(0, min(x, w - 1))
        target_y = max(0, min(y, h - 1))

        if smooth:
            cur_x, cur_y = self.get_pointer_position()
            steps = 15
            for i in range(1, steps + 1):
                nx = int(cur_x + (target_x - cur_x) * (i / steps))
                ny = int(cur_y + (target_y - cur_y) * (i / steps))
                self.root.warp_pointer(nx, ny)
                self.display.sync()
                time.sleep(0.01)
        else:
            self.root.warp_pointer(target_x, target_y)
            self.display.sync()

    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left", clicks: int = 1):
        """
        Click the specified mouse button at (x, y) or current location.
        Buttons: 'left' (1), 'middle' (2), 'right' (3).
        """
        if x is not None and y is not None:
            self.move_mouse(x, y)

        button_map = {
            "left": 1,
            "middle": 2,
            "right": 3,
        }
        btn_code = button_map.get(button.lower().strip(), 1)

        for _ in range(clicks):
            self.xtest.fake_input(self.display, self.X.ButtonPress, btn_code)
            self.display.sync()
            time.sleep(0.04)
            self.xtest.fake_input(self.display, self.X.ButtonRelease, btn_code)
            self.display.sync()
            if clicks > 1:
                time.sleep(0.06)

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, button: str = "left"):
        """Drag mouse cursor from start to end with button pressed."""
        self.move_mouse(start_x, start_y)
        time.sleep(0.05)

        button_map = {"left": 1, "middle": 2, "right": 3}
        btn_code = button_map.get(button.lower().strip(), 1)

        self.xtest.fake_input(self.display, self.X.ButtonPress, btn_code)
        self.display.sync()
        time.sleep(0.05)

        # Smooth drag
        steps = 20
        for i in range(1, steps + 1):
            nx = int(start_x + (end_x - start_x) * (i / steps))
            ny = int(start_y + (end_y - start_y) * (i / steps))
            self.root.warp_pointer(nx, ny)
            self.display.sync()
            time.sleep(0.01)

        time.sleep(0.05)
        self.xtest.fake_input(self.display, self.X.ButtonRelease, btn_code)
        self.display.sync()

    def scroll(self, clicks: int = 3, direction: str = "down"):
        """
        Scroll mouse wheel.
        Direction: 'down' (Button 5) or 'up' (Button 4).
        """
        btn_code = 5 if direction.lower() == "down" else 4
        for _ in range(abs(clicks)):
            self.xtest.fake_input(self.display, self.X.ButtonPress, btn_code)
            self.xtest.fake_input(self.display, self.X.ButtonRelease, btn_code)
            self.display.sync()
            time.sleep(0.03)

    def _get_keycode(self, key_name: str) -> int:
        """Resolve key name into X11 keycode."""
        key_aliases = {
            "enter": "Return",
            "return": "Return",
            "esc": "Escape",
            "escape": "Escape",
            "backspace": "BackSpace",
            "tab": "Tab",
            "space": "space",
            "ctrl": "Control_L",
            "control": "Control_L",
            "alt": "Alt_L",
            "shift": "Shift_L",
            "super": "Super_L",
            "win": "Super_L",
            "windows": "Super_L",
            "up": "Up",
            "down": "Down",
            "left": "Left",
            "right": "Right",
            "home": "Home",
            "end": "End",
            "pageup": "Prior",
            "pagedown": "Next",
            "delete": "Delete",
            "capslock": "Caps_Lock",
        }

        lookup = key_aliases.get(key_name.lower(), key_name)
        keysym = self.XK.string_to_keysym(lookup)
        if keysym == 0 and len(key_name) == 1:
            keysym = ord(key_name)

        keycode = self.display.keysym_to_keycode(keysym)
        return keycode

    def press_key(self, key_name: str):
        """Press and release a single key."""
        keycode = self._get_keycode(key_name)
        if keycode == 0:
            console.print(f"[yellow]⚠️ Unknown key: {key_name}[/yellow]")
            return

        self.xtest.fake_input(self.display, self.X.KeyPress, keycode)
        self.display.sync()
        time.sleep(0.03)
        self.xtest.fake_input(self.display, self.X.KeyRelease, keycode)
        self.display.sync()

    def press_hotkey(self, combo: Union[str, List[str]]):
        """
        Press a hotkey combination (e.g. 'ctrl+c', 'alt+tab', 'super', 'ctrl+shift+t').
        """
        if isinstance(combo, str):
            keys = [k.strip() for k in combo.replace("-", "+").split("+")]
        else:
            keys = combo

        keycodes = []
        for k in keys:
            code = self._get_keycode(k)
            if code != 0:
                keycodes.append(code)

        # Press down in order
        for code in keycodes:
            self.xtest.fake_input(self.display, self.X.KeyPress, code)
            self.display.sync()
            time.sleep(0.02)

        time.sleep(0.05)

        # Release in reverse order
        for code in reversed(keycodes):
            self.xtest.fake_input(self.display, self.X.KeyRelease, code)
            self.display.sync()
            time.sleep(0.02)

    def type_text(self, text: str, delay: float = 0.02):
        """Type arbitrary text string into the currently focused window."""
        for char in text:
            if char == "\n":
                self.press_key("Return")
            elif char == "\t":
                self.press_key("Tab")
            elif char == " ":
                self.press_key("space")
            else:
                is_upper = char.isupper() or char in '~!@#$%^&*()_+{}|:"<>?'
                if is_upper:
                    shift_code = self._get_keycode("Shift_L")
                    self.xtest.fake_input(self.display, self.X.KeyPress, shift_code)
                    self.display.sync()

                code = self._get_keycode(char)
                if code != 0:
                    self.xtest.fake_input(self.display, self.X.KeyPress, code)
                    self.display.sync()
                    time.sleep(0.01)
                    self.xtest.fake_input(self.display, self.X.KeyRelease, code)
                    self.display.sync()

                if is_upper:
                    self.xtest.fake_input(self.display, self.X.KeyRelease, shift_code)
                    self.display.sync()

            if delay > 0:
                time.sleep(delay)


# Global singleton controller
_controller: Optional[InputController] = None


def get_input_controller() -> InputController:
    global _controller
    if _controller is None:
        _controller = InputController()
    return _controller


# ==========================================
# Tool Functions for Victoria's Brain
# ==========================================

def mouse_click(x: Optional[int] = None, y: Optional[int] = None, button: str = "left", clicks: int = 1) -> str:
    """Click mouse at (x, y) or current pointer location."""
    ctrl = get_input_controller()
    ctrl.click(x=x, y=y, button=button, clicks=clicks)
    px, py = ctrl.get_pointer_position()
    return f"Mouse {button} clicked {clicks} time(s) at ({px}, {py})."


def mouse_move(x: int, y: int, smooth: bool = True) -> str:
    """Move mouse pointer to (x, y) coordinates."""
    ctrl = get_input_controller()
    ctrl.move_mouse(x=x, y=y, smooth=smooth)
    return f"Mouse pointer moved to ({x}, {y})."


def mouse_drag(start_x: int, start_y: int, end_x: int, end_y: int, button: str = "left") -> str:
    """Drag mouse from (start_x, start_y) to (end_x, end_y)."""
    ctrl = get_input_controller()
    ctrl.drag(start_x, start_y, end_x, end_y, button=button)
    return f"Mouse dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})."


def mouse_scroll(clicks: int = 3, direction: str = "down") -> str:
    """Scroll mouse wheel up or down."""
    ctrl = get_input_controller()
    ctrl.scroll(clicks=clicks, direction=direction)
    return f"Mouse scrolled {direction} by {clicks} steps."


def get_mouse_position() -> Dict[str, Any]:
    """Get current mouse cursor position and screen dimensions."""
    ctrl = get_input_controller()
    x, y = ctrl.get_pointer_position()
    w, h = ctrl.get_screen_size()
    return {"x": x, "y": y, "screen_width": w, "screen_height": h}


def keyboard_type(text: str, delay: float = 0.02) -> str:
    """Type text into currently focused application."""
    ctrl = get_input_controller()
    ctrl.type_text(text, delay=delay)
    return f"Typed {len(text)} characters into active window."


def keyboard_hotkey(hotkey: str) -> str:
    """Trigger a keyboard hotkey combination (e.g. 'ctrl+c', 'alt+tab', 'super', 'ctrl+alt+t')."""
    ctrl = get_input_controller()
    ctrl.press_hotkey(hotkey)
    return f"Triggered hotkey: '{hotkey}'."


def keyboard_press(key: str) -> str:
    """Press a single key (e.g. 'Enter', 'Escape', 'BackSpace', 'Tab', 'Space', 'Up', 'Down')."""
    ctrl = get_input_controller()
    ctrl.press_key(key)
    return f"Pressed key: '{key}'."
