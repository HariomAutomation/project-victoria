"""
Victoria MCP Server
===================
Exposes Victoria's brain (chat, models, memory, tools, speech) to any
MCP-compatible AI client over stdio JSON-RPC 2.0 (newline-delimited).

Run:
    victoria-mcp                 # console script (pip install -e .)
    python -m victoria.mcp.server

Example client configuration (opencode.json / claude_desktop_config.json):

    {
      "mcpServers": {
        "victoria": { "command": "victoria-mcp" }
      }
    }

Safety:
    - Dangerous tools are fail-closed: they only run when
      `mcp.victoria_server.allow_dangerous_tools: true` is set in
      config/victoria.yaml.
    - The JSON-RPC protocol uses the process's real stdout. Every rich/log
      print is redirected to stderr so it can never corrupt the channel.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Optional

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "victoria"
SERVER_VERSION = "2.0.0"


def log(message: str) -> None:
    """Diagnostics go to stderr only — stdout is the JSON-RPC channel."""
    print(f"[victoria-mcp] {message}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Tool schemas (JSON Schema for every tool exposed over MCP)
# ---------------------------------------------------------------------------

_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "victoria_chat",
        "description": (
            "Send a message or task to Victoria's brain and get her reply. "
            "Uses her active AI model with her persona, owner memory and tools."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message / task for Victoria"},
                "speak": {
                    "type": "boolean",
                    "description": "Also speak her reply out loud (default false)",
                    "default": False,
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "victoria_list_models",
        "description": "List Victoria's configured AI models and show which one is active.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "victoria_switch_model",
        "description": (
            "Switch Victoria's active brain model "
            "(e.g. 'gemini', 'opencode', 'openrouter', 'local_fast')."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Config model key to activate"},
            },
            "required": ["model"],
        },
    },
    {
        "name": "victoria_status",
        "description": (
            "Report Victoria's status: active model, tools loaded, owner memory "
            "stats and voice enrollment state."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "victoria_run_tool",
        "description": (
            "Run one of Victoria's built-in system tools directly. Dangerous "
            "tools follow the MCP safety switch and are denied by default."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool": {"type": "string", "description": "Tool name"},
                "arguments": {
                    "type": "object",
                    "description": "Arguments object for the tool",
                    "additionalProperties": True,
                },
            },
            "required": ["tool"],
        },
    },
    {
        "name": "victoria_remember",
        "description": "Store a fact, preference or note in Victoria's persistent owner memory vault.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Memory text to store"},
                "category": {
                    "type": "string",
                    "description": "fact | preference | intention | project | event | note",
                    "default": "fact",
                },
                "title": {"type": "string", "description": "Short title (optional)", "default": ""},
                "importance": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "1 (minor) to 5 (critical)",
                    "default": 3,
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "victoria_recall",
        "description": "Search Victoria's owner memory vault (facts, preferences, past projects).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (empty = recent memories)"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
        },
    },
    {
        "name": "victoria_speak",
        "description": "Make Victoria speak the given text aloud through her TTS voice.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to speak"},
            },
            "required": ["text"],
        },
    },
]


# ---------------------------------------------------------------------------
# Backend: lazy facade over Victoria's brain / tools / memory / voice
# ---------------------------------------------------------------------------

class VictoriaBackend:
    """Lazily-initialized bridge into Victoria's internals."""

    def __init__(self):
        self._router = None
        self._registry = None

    # -- internals ----------------------------------------------------------

    def _confirm_dangerous(self, tool_name: str, arguments: dict) -> bool:
        """Fail-closed confirmation for dangerous tools over MCP."""
        try:
            from victoria.config import get_config
            allowed = bool(get_config().get("mcp.victoria_server.allow_dangerous_tools", False))
        except Exception:
            allowed = False
        if not allowed:
            log(f"Dangerous tool '{tool_name}' blocked (mcp.victoria_server.allow_dangerous_tools=false)")
        return allowed

    def _ensure_tools(self):
        if self._registry is None:
            from victoria.brain.tools import build_tool_registry
            self._registry = build_tool_registry()
        return self._registry

    def _ensure_router(self):
        if self._router is None:
            from victoria.brain.router import BrainRouter
            registry = self._ensure_tools()
            self._router = BrainRouter(tool_registry=registry)
            self._router.confirm_callback = self._confirm_dangerous
        return self._router

    # -- tools --------------------------------------------------------------

    def tool_chat(self, message: str, speak: bool = False) -> str:
        if not message or not str(message).strip():
            return "Error: 'message' cannot be empty."
        router = self._ensure_router()
        reply = router.think(str(message))
        if not reply or not str(reply).strip():
            reply = "Victoria produced an empty reply."
        if speak:
            try:
                self.tool_speak(reply)
            except Exception as e:  # noqa: BLE001
                reply = f"{reply}\n\n[Note: speech playback failed: {e}]"
        return reply

    def tool_list_models(self) -> str:
        from victoria.config import get_config
        cfg = get_config()
        active = cfg.get_active_model_name()
        lines = [f"Active model: {active}", "", "Configured models:"]
        for name in cfg.get("brain.models", {}):
            try:
                mc = cfg.get_model_config(name)
                marker = "*" if name == active else " "
                lines.append(f" {marker} {name} -> {mc.get('model')} (provider: {mc.get('provider')})")
            except Exception as e:  # noqa: BLE001
                lines.append(f"    {name} -> error: {e}")
        return "\n".join(lines)

    def tool_switch_model(self, model: str) -> str:
        from victoria.config import get_config
        cfg = get_config()
        models = cfg.get("brain.models", {})
        key = str(model or "").strip()
        if key not in models:
            return f"Unknown model '{key}'. Available: {', '.join(models)}"
        router = self._ensure_router()
        router.switch_model(key)
        cfg.set_active_model(key, persist=True)
        model_id = cfg.get_model_config(key).get("model")
        return f"Victoria's brain switched to '{key}' ({model_id})."

    def tool_status(self) -> str:
        from victoria.config import get_config
        cfg = get_config()
        lines = ["Victoria Status", "==============="]
        try:
            active = cfg.get_active_model_name()
            mc = cfg.get_model_config(active)
            lines.append(f"Active model key : {active}")
            lines.append(f"Model id         : {mc.get('model')}")
            lines.append(f"Provider         : {mc.get('provider')}")
        except Exception as e:  # noqa: BLE001
            lines.append(f"Model info       : unavailable ({e})")
        lines.append(
            "Tools loaded     : "
            + (str(len(self._registry.list_tools())) if self._registry is not None else "lazy (not initialized yet)")
        )
        try:
            from victoria.brain.owner_memory import get_owner_vault
            stats = get_owner_vault().get_stats()
            lines.append(f"Owner memory     : {stats}")
        except Exception as e:  # noqa: BLE001
            lines.append(f"Owner memory     : unavailable ({e})")
        try:
            from victoria.voice.speaker_verify import SpeakerVerifier
            lines.append(f"Voice enrolled   : {SpeakerVerifier().is_enrolled()}")
        except Exception as e:  # noqa: BLE001
            lines.append(f"Voice enrolled   : unavailable ({e})")
        return "\n".join(lines)

    def tool_run_tool(self, tool: str, arguments: Optional[dict] = None) -> str:
        name = str(tool or "").strip()
        if not name:
            return "Error: 'tool' cannot be empty."
        args = arguments or {}
        if not isinstance(args, dict):
            return "Error: 'arguments' must be a JSON object."
        registry = self._ensure_tools()
        known = registry.list_tools()
        if name not in known:
            return f"Unknown tool '{name}'. {len(known)} tools available."
        if registry.is_dangerous(name) and not self._confirm_dangerous(name, args):
            return (
                f"⛔ '{name}' is a dangerous tool and is blocked for MCP clients. "
                "Set mcp.victoria_server.allow_dangerous_tools=true to permit it."
            )
        result = registry.execute(name, args)
        return str(result)

    def tool_remember(
        self,
        content: str,
        category: str = "fact",
        title: str = "",
        importance: int = 3,
    ) -> str:
        text = str(content or "").strip()
        if not text:
            return "Error: 'content' cannot be empty."
        try:
            importance = max(1, min(5, int(importance)))
        except (TypeError, ValueError):
            importance = 3
        from victoria.brain.owner_memory import get_owner_vault
        mem_id = get_owner_vault().store(
            content=text,
            category=str(category or "fact"),
            title=str(title or ""),
            importance=importance,
        )
        return f"Remembered (memory id {mem_id}): {text}"

    def tool_recall(self, query: str = "", limit: int = 5) -> str:
        try:
            limit = max(1, min(20, int(limit)))
        except (TypeError, ValueError):
            limit = 5
        q = str(query or "").strip()
        from victoria.brain.owner_memory import get_owner_vault
        vault = get_owner_vault()
        parts = []
        if q:
            try:
                ctx = vault.get_relevant_context(q, max_items=limit)
                if ctx and str(ctx).strip():
                    parts.append(str(ctx))
            except Exception:  # noqa: BLE001
                pass
        try:
            rows = vault.search(q, limit=limit)
            if rows:
                lines = [
                    f"- [{r.get('category')}] {r.get('title')}: {str(r.get('content'))[:280]}"
                    for r in rows
                ]
                parts.append("Matching memories:\n" + "\n".join(lines))
        except Exception as e:  # noqa: BLE001
            parts.append(f"Memory search error: {e}")
        return "\n\n".join(parts) if parts else "No matching memories found."

    def tool_speak(self, text: str) -> str:
        spoken = str(text or "").strip()
        if not spoken:
            return "Error: 'text' cannot be empty."
        from victoria.voice.tts import get_tts
        get_tts().speak(spoken, blocking=False)
        return f"Victoria is speaking: {spoken}"


# ---------------------------------------------------------------------------
# MCP server (JSON-RPC 2.0 over stdio)
# ---------------------------------------------------------------------------

class MCPServer:
    """Minimal, dependency-free MCP stdio server."""

    def __init__(self, out_stream=None):
        self._out = out_stream if out_stream is not None else sys.stdout
        self.backend = VictoriaBackend()
        self._stop = False

    # -- protocol plumbing ---------------------------------------------------

    def _send(self, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False, default=str)
        self._out.write(data + "\n")
        try:
            self._out.flush()
        except Exception:  # noqa: BLE001
            pass

    def _result(self, msg_id: Any, result: Any) -> None:
        self._send({"jsonrpc": "2.0", "id": msg_id, "result": result})

    def _error(self, msg_id: Any, code: int, message: str) -> None:
        self._send({"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}})

    def _tool_handlers(self) -> dict:
        return {
            "victoria_chat": self.backend.tool_chat,
            "victoria_list_models": self.backend.tool_list_models,
            "victoria_switch_model": self.backend.tool_switch_model,
            "victoria_status": self.backend.tool_status,
            "victoria_run_tool": self.backend.tool_run_tool,
            "victoria_remember": self.backend.tool_remember,
            "victoria_recall": self.backend.tool_recall,
            "victoria_speak": self.backend.tool_speak,
        }

    # -- message handling ------------------------------------------------------

    def handle_message(self, msg: dict) -> None:
        method = msg.get("method")
        msg_id = msg.get("id")
        has_id = "id" in msg

        if method == "initialize":
            if has_id:
                self._result(msg_id, {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                })
        elif method in ("notifications/initialized", "initialized", "notifications/cancelled"):
            return
        elif method == "ping":
            if has_id:
                self._result(msg_id, {})
        elif method == "tools/list":
            if has_id:
                self._result(msg_id, {"tools": _TOOL_SCHEMAS})
        elif method == "tools/call":
            if not has_id:
                return
            params = msg.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            handler = self._tool_handlers().get(name)
            if handler is None:
                self._error(msg_id, -32602, f"Unknown tool: {name}")
                return
            if not isinstance(arguments, dict):
                arguments = {}
            try:
                text = handler(**arguments)
                result = {"content": [{"type": "text", "text": str(text)}], "isError": False}
            except TypeError as e:
                result = {
                    "content": [{"type": "text", "text": f"Invalid arguments for '{name}': {e}"}],
                    "isError": True,
                }
            except Exception as e:  # noqa: BLE001
                result = {
                    "content": [{"type": "text", "text": f"'{name}' failed: {e}"}],
                    "isError": True,
                }
            self._result(msg_id, result)
        elif method == "resources/list":
            if has_id:
                self._result(msg_id, {"resources": []})
        elif method == "prompts/list":
            if has_id:
                self._result(msg_id, {"prompts": []})
        elif method == "logging/setLevel":
            if has_id:
                self._result(msg_id, {})
        elif method in ("shutdown", "exit"):
            if has_id:
                self._result(msg_id, {})
            self._stop = True
        else:
            if has_id:
                self._error(msg_id, -32601, f"Method not found: {method}")

    def serve_forever(self) -> None:
        while not self._stop:
            line = sys.stdin.readline()
            if not line:  # EOF: client closed the pipe
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self._error(None, -32700, "Parse error")
                continue
            if not isinstance(msg, dict):
                self._error(None, -32600, "Invalid Request")
                continue
            try:
                self.handle_message(msg)
            except Exception as e:  # noqa: BLE001
                if "id" in msg:
                    self._error(msg.get("id"), -32603, f"Internal error: {e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    # The MCP protocol owns stdout. Redirect everything else (rich consoles,
    # print statements, library logs that use sys.stdout) to stderr first.
    real_stdout = sys.stdout
    sys.stdout = sys.stderr

    try:
        from victoria.config import get_config
        if get_config().get("mcp.victoria_server.enabled", True) is False:
            log("Disabled via config (mcp.victoria_server.enabled=false). Exiting.")
            return 0
    except Exception as e:  # noqa: BLE001
        log(f"Config load notice: {e}")

    log(f"Victoria MCP server ready (protocol {PROTOCOL_VERSION}).")
    server = MCPServer(out_stream=real_stdout)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
