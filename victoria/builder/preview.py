"""
Victoria - Live Preview Server (Phase 3)
Lightweight HTTP server to preview reverse-engineered web apps and mock APIs.
"""

import http.server
import socketserver
import threading
from pathlib import Path
from typing import Optional
from rich.console import Console

console = Console()


class LivePreviewServer:
    """
    Manages live HTTP preview servers for reconstructed frontends and mock APIs.
    """

    def __init__(self):
        self._server: Optional[socketserver.TCPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.port: int = 5173
        self.directory: str = ""

    def start(self, directory: str, port: int = 5173) -> str:
        """
        Start serving the specified directory on the given port in a background thread.
        """
        if self._server:
            self.stop()

        self.port = port
        self.directory = str(Path(directory).resolve())

        class CustomHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=directory, **kwargs)

        try:
            # Allow address reuse
            socketserver.TCPServer.allow_reuse_address = True
            self._server = socketserver.TCPServer(("", port), CustomHandler)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()

            url = f"http://localhost:{port}"
            console.print(f"[bold green]🌐 Live preview server running at: {url}[/bold green]")
            return f"Preview server live at {url} (serving {directory})"
        except Exception as e:
            console.print(f"[red]❌ Failed to start preview server: {e}[/red]")
            return f"Error starting server: {e}"

    def stop(self) -> str:
        """Stop running preview server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None
            console.print("[yellow]🛑 Preview server stopped.[/yellow]")
            return "Preview server stopped."
        return "No preview server is running."
