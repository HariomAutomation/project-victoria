"""
Victoria - Voice Events & IPC Bridge
Broadcasts voice pipeline states (wake, listening, thinking, speaking, standby)
over lightweight local UDP datagrams to the Floating Desktop HUD, Web HUD, and other listeners.
"""

import json
import socket
import threading
from typing import Optional, Callable

EVENT_PORT = 49380     # Outbound state broadcasts (Victoria -> Widgets/HUD)
COMMAND_PORT = 49381   # Inbound commands (Widgets -> Victoria)


class VoiceEventBroadcaster:
    """Publishes state events from Victoria's voice loop to all local listeners."""

    def __init__(self, port: int = EVENT_PORT):
        self.port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Enable broadcast if needed, otherwise localhost is fine
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def emit(self, event_type: str, **kwargs):
        """Send an event datagram to localhost."""
        payload = {
            "event": event_type,
            **kwargs,
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            self._sock.sendto(data, ("127.0.0.1", self.port))
        except Exception:
            pass

    def wake(self, phrase: str = "Victoria"):
        self.emit("wake", state="listening", phrase=phrase)

    def listening(self, level: float = 0.0):
        self.emit("listening", state="listening", level=level)

    def thinking(self, text: Optional[str] = None):
        self.emit("thinking", state="thinking", prompt=text or "")

    def speaking(self, text: str = ""):
        self.emit("speaking", state="speaking", text=text)

    def standby(self):
        self.emit("standby", state="standby")


class VoiceEventListener:
    """Listens for Victoria voice events in background thread or GUI event loop."""

    def __init__(self, on_event: Callable[[dict], None], port: int = EVENT_PORT):
        self.on_event = on_event
        self.port = port
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None

    def start(self):
        self._running = True
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", self.port))
        self._sock.settimeout(0.5)

        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def _listen_loop(self):
        while self._running:
            try:
                data, _ = self._sock.recvfrom(4096)
                if data:
                    payload = json.loads(data.decode("utf-8"))
                    self.on_event(payload)
            except socket.timeout:
                continue
            except Exception:
                continue

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass


# Global singleton broadcaster for easy access throughout the engine
broadcaster = VoiceEventBroadcaster()
