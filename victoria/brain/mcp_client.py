"""
Victoria - Minimal MCP (Model Context Protocol) stdio client.

Lets Victoria talk to any local MCP server over stdio — in particular
morluto/rea (`npx -y rea-agents mcp`), so her brain can call REA's
reverse-engineering tools directly.

Speaks JSON-RPC 2.0, newline-delimited, over the server's stdin/stdout:
    initialize -> notifications/initialized -> tools/list -> tools/call

A background reader thread feeds a queue so interleaved server
notifications/logs don't desync request/response matching.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from typing import Any, Optional

from rich.console import Console

console = Console()

DEFAULT_PROTOCOL_VERSION = "2024-11-05"


class MCPError(Exception):
    """Raised for any MCP transport/protocol failure."""


class MCPStdioClient:
    """A synchronous MCP client over a stdio subprocess."""

    def __init__(
        self,
        command: str,
        args: Optional[list[str]] = None,
        env: Optional[dict] = None,
        cwd: Optional[str] = None,
        name: str = "mcp",
        request_timeout: int = 300,
        protocol_version: str = DEFAULT_PROTOCOL_VERSION,
    ):
        self.command = command
        self.args = args or []
        self.env = {**os.environ, **(env or {})}
        self.cwd = cwd
        self.name = name
        self.request_timeout = request_timeout
        self.protocol_version = protocol_version

        self._proc: Optional[subprocess.Popen] = None
        self._q: "queue.Queue[Optional[dict]]" = queue.Queue()
        self._id = 0
        self._lock = threading.Lock()
        self._stderr_lines: list[str] = []
        self.server_info: dict = {}

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> "MCPStdioClient":
        if self._proc is not None:
            return self
        try:
            self._proc = subprocess.Popen(
                [self.command, *self.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=self.env,
                cwd=self.cwd,
            )
        except FileNotFoundError as e:
            raise MCPError(f"'{self.command}' not found on PATH ({e})")
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        return self

    def _read_stdout(self):
        try:
            for line in self._proc.stdout:  # type: ignore[union-attr]
                line = line.strip()
                if not line:
                    continue
                try:
                    self._q.put(json.loads(line))
                except json.JSONDecodeError:
                    continue  # non-JSON noise on stdout
        except Exception:
            pass
        finally:
            self._q.put(None)  # sentinel: stream closed

    def _read_stderr(self):
        try:
            for line in self._proc.stderr:  # type: ignore[union-attr]
                self._stderr_lines.append(line.rstrip())
                if len(self._stderr_lines) > 200:
                    self._stderr_lines.pop(0)
        except Exception:
            pass

    def _send(self, obj: dict):
        if not self._proc or not self._proc.stdin:
            raise MCPError("server not started")
        with self._lock:
            self._proc.stdin.write(json.dumps(obj) + "\n")
            self._proc.stdin.flush()

    def _request(self, method: str, params: Optional[dict] = None, timeout: Optional[int] = None) -> Any:
        self._id += 1
        rid = self._id
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})

        deadline = time.time() + (timeout or self.request_timeout)
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise MCPError(f"{method}: timed out after {timeout or self.request_timeout}s")
            try:
                msg = self._q.get(timeout=remaining)
            except queue.Empty:
                raise MCPError(f"{method}: timed out after {timeout or self.request_timeout}s")
            if msg is None:
                tail = " | ".join(self._stderr_lines[-3:])
                raise MCPError(f"{method}: server closed the connection. stderr: {tail}")
            if msg.get("id") == rid:
                if "error" in msg:
                    raise MCPError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            # otherwise it is a notification / unrelated message -> ignore

    # -- protocol ----------------------------------------------------------

    def initialize(self) -> dict:
        res = self._request("initialize", {
            "protocolVersion": self.protocol_version,
            "capabilities": {},
            "clientInfo": {"name": "victoria", "version": "0.2.0"},
        })
        self.server_info = (res or {}).get("serverInfo", {}) or {}
        # Required handshake follow-up notification (no id).
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return res or {}

    def list_tools(self) -> list[dict]:
        res = self._request("tools/list", {})
        return (res or {}).get("tools", []) or []

    def call_tool(self, name: str, arguments: Optional[dict] = None, timeout: Optional[int] = None) -> dict:
        return self._request("tools/call", {"name": name, "arguments": arguments or {}}, timeout=timeout) or {}

    def stop(self):
        try:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=5)
                except Exception:
                    self._proc.kill()
        except Exception:
            pass
        finally:
            self._proc = None


def result_to_text(result: dict) -> str:
    """Flatten an MCP tools/call result into a plain string for the brain."""
    parts: list[str] = []
    for item in result.get("content", []) or []:
        ctype = item.get("type")
        if ctype == "text":
            parts.append(item.get("text", ""))
        elif ctype == "resource":
            parts.append(json.dumps(item.get("resource", {})))
        else:
            parts.append(json.dumps(item))
    text = "\n".join(p for p in parts if p)
    if not text:
        text = json.dumps(result)
    if result.get("isError"):
        return f"⚠️ MCP tool error: {text}"
    return text
