"""
Victoria - MCP (Model Context Protocol) integration.

This package exposes Victoria's brain to external AI clients over the
standard MCP stdio transport, so tools like Claude Desktop, OpenCode,
Cursor or custom agents can chat with her, switch her models, use her
memory vault, run her Linux tools and make her speak.
"""

from victoria.mcp.server import MCPServer, main  # noqa: F401

__all__ = ["MCPServer", "main"]
