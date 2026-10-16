"""
Victoria - MCP Bridge
Connects configured MCP servers (e.g. morluto/rea) and exposes their tools to
Victoria's brain, so she can call them exactly like her built-in tools.

Each MCP tool is registered as `<prefix>_<toolname>` (e.g. `rea_open_binary`)
and carries the server's real JSON schema, which the providers pass through to
the model unchanged.
"""

from __future__ import annotations

from typing import Any, Optional

from rich.console import Console

from victoria.brain.mcp_client import MCPStdioClient, MCPError, result_to_text

console = Console()


def _make_caller(client: MCPStdioClient, remote_tool: str):
    """Return a callable that forwards kwargs to the MCP tool."""
    def _call(**kwargs):
        try:
            res = client.call_tool(remote_tool, kwargs)
            return result_to_text(res)
        except MCPError as e:
            return f"MCP call failed: {e}"
        except Exception as e:  # noqa: BLE001
            return f"MCP call error: {e}"
    return _call


def connect_and_register(registry, spec: dict, default_prefix: Optional[str] = None) -> Optional[dict]:
    """Start one MCP server, list its tools, and register them into the registry."""
    name = spec.get("name", "mcp")
    command = spec.get("command")
    if not command:
        console.print(f"[yellow]⚠️ MCP '{name}' has no command; skipping.[/yellow]")
        return None

    prefix = spec.get("tool_prefix", default_prefix or name)

    client = MCPStdioClient(
        command=command,
        args=spec.get("args", []),
        env=spec.get("env"),
        cwd=spec.get("cwd"),
        name=name,
        request_timeout=spec.get("timeout", 300),
    )
    client.start()
    client.initialize()
    tools = client.list_tools()

    registered: list[str] = []
    for t in tools:
        remote = t.get("name", "")
        if not remote:
            continue
        tool_name = f"{prefix}_{remote}" if prefix else remote
        schema = t.get("inputSchema") or {"type": "object", "properties": {}}
        registry.register(
            name=tool_name,
            description=(t.get("description") or f"MCP tool '{remote}'")[:1024],
            parameters=[],
            function=_make_caller(client, remote),
            category="mcp",
            dangerous=True,
            raw_schema=schema,
        )
        registered.append(tool_name)

    # Keep the client alive for the lifetime of the registry.
    registry._mcp_clients.append(client)

    server_name = (client.server_info or {}).get("name", name)
    console.print(f"[green]✅ MCP '{server_name}': {len(registered)} tools registered[/green]")
    return {"name": name, "client": client, "tools": registered, "server_info": client.server_info}


def load_mcp_servers(registry, mcp_config: Optional[dict]) -> list[dict]:
    """Connect every enabled MCP server in config. Never raises — failures are logged."""
    if not mcp_config or not mcp_config.get("enabled", False):
        return []

    servers = mcp_config.get("servers", {}) or {}
    results: list[dict] = []
    for name, spec in servers.items():
        if not isinstance(spec, dict) or not spec.get("enabled", True):
            continue
        merged = {**spec, "name": name}
        try:
            cmd = f"{merged.get('command')} {' '.join(merged.get('args', []))}".strip()
            console.print(f"[cyan]🔌 Connecting MCP server '{name}' → {cmd}[/cyan]")
            res = connect_and_register(registry, merged)
            if res:
                results.append(res)
        except Exception as e:  # noqa: BLE001 - one bad server must not break startup
            console.print(f"[yellow]⚠️ MCP server '{name}' unavailable: {e}[/yellow]")
    return results
