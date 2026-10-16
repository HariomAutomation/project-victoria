"""
Victoria - Tool Registry & Definitions
Registers all Linux control tools that Victoria's brain can call.
Each tool is a callable function with metadata for the AI model.
"""

import json
from typing import Any, Callable, Optional
from rich.console import Console

from victoria.brain.providers.base_provider import ToolDefinition, ToolParameter

console = Console()


class ToolRegistry:
    """
    Central registry for all tools Victoria can use.

    Tools are Python functions decorated with metadata that gets sent
    to the AI model as function declarations. When the model decides
    to call a tool, the registry executes the corresponding function.
    """

    def __init__(self):
        self._tools: dict[str, dict] = {}  # name -> {definition, function}

    def register(
        self,
        name: str,
        description: str,
        parameters: list[ToolParameter],
        function: Callable,
        category: str = "general",
        dangerous: bool = False,
    ):
        """Register a tool."""
        self._tools[name] = {
            "definition": ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                category=category,
                dangerous=dangerous,
            ),
            "function": function,
        }

    def get_definitions(self, categories: Optional[list[str]] = None) -> list[ToolDefinition]:
        """Get all tool definitions, optionally filtered by category."""
        defs = [t["definition"] for t in self._tools.values()]
        if categories:
            defs = [d for d in defs if d.category in categories]
        return defs

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """
        Execute a tool by name with the given arguments.

        Returns:
            String result of the tool execution (always stringified for the AI)
        """
        if tool_name not in self._tools:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        tool = self._tools[tool_name]
        func = tool["function"]

        try:
            console.print(f"[yellow]⚡ Executing tool: {tool_name}({arguments})[/yellow]")
            result = func(**arguments)
            result_str = json.dumps(result) if not isinstance(result, str) else result
            console.print(f"[green]✅ Tool result: {result_str[:200]}[/green]")
            return result_str
        except Exception as e:
            error = f"Tool execution error: {str(e)}"
            console.print(f"[red]❌ {error}[/red]")
            return json.dumps({"error": error})

    def is_dangerous(self, tool_name: str) -> bool:
        """Check if a tool is marked as dangerous."""
        if tool_name in self._tools:
            return self._tools[tool_name]["definition"].dangerous
        return False

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())


def build_tool_registry() -> ToolRegistry:
    """
    Build and return a ToolRegistry with all Victoria's Linux tools registered.
    This is the central place where all tools are wired up.
    """
    registry = ToolRegistry()

    # Import all tool modules
    from victoria.tools import (
        app_launcher,
        terminal,
        audio_control,
        brightness,
        file_manager,
        screenshot,
        system_info,
        media_player,
        clipboard,
        custom_scripts,
        leantoken_tool,
        persona_tool,
        owner_memory_tool,
    )

    # ==========================================
    # 1. App Launcher
    # ==========================================
    registry.register(
        name="open_application",
        description="Open/launch an application by its name. Examples: firefox, nautilus, code, terminal, gedit, calculator",
        parameters=[
            ToolParameter(name="app_name", type="string", description="Name of the application to open (e.g., 'firefox', 'nautilus', 'code', 'gedit')"),
        ],
        function=app_launcher.open_application,
        category="system",
    )

    registry.register(
        name="close_application",
        description="Close/kill an application by its name or window title",
        parameters=[
            ToolParameter(name="app_name", type="string", description="Name of the application or window to close"),
        ],
        function=app_launcher.close_application,
        category="system",
    )

    registry.register(
        name="list_running_apps",
        description="List all currently running GUI applications and their window titles",
        parameters=[],
        function=app_launcher.list_running_apps,
        category="system",
    )

    # ==========================================
    # 2. Terminal Commands
    # ==========================================
    registry.register(
        name="run_terminal_command",
        description="Execute a terminal/shell command and return the output. Use for any Linux command like ls, cat, grep, find, etc.",
        parameters=[
            ToolParameter(name="command", type="string", description="The shell command to execute"),
            ToolParameter(name="timeout", type="integer", description="Timeout in seconds", required=False),
        ],
        function=terminal.run_command,
        category="system",
        dangerous=True,
    )

    # ==========================================
    # 3. Volume Control
    # ==========================================
    registry.register(
        name="set_volume",
        description="Set the system audio volume to a specific percentage (0-100) or adjust relatively (+10, -10)",
        parameters=[
            ToolParameter(name="level", type="string", description="Volume level: '50' for 50%, '+10' to increase by 10%, '-10' to decrease, 'mute', 'unmute'"),
        ],
        function=audio_control.set_volume,
        category="media",
    )

    registry.register(
        name="get_volume",
        description="Get the current system volume level",
        parameters=[],
        function=audio_control.get_volume,
        category="media",
    )

    registry.register(
        name="toggle_mute",
        description="Toggle the system mute state: mute if currently unmuted, unmute otherwise",
        parameters=[],
        function=audio_control.toggle_mute,
        category="media",
    )

    # ==========================================
    # 4. Brightness
    # ==========================================
    registry.register(
        name="set_brightness",
        description="Set screen brightness to a percentage (1-100) or adjust relatively (+10, -10)",
        parameters=[
            ToolParameter(name="level", type="string", description="Brightness level: '50' for 50%, '+10' to increase, '-10' to decrease"),
        ],
        function=brightness.set_brightness,
        category="system",
    )

    registry.register(
        name="get_brightness",
        description="Get the current screen brightness level",
        parameters=[],
        function=brightness.get_brightness,
        category="system",
    )

    # ==========================================
    # 5. File Manager
    # ==========================================
    registry.register(
        name="search_files",
        description="Search for files and directories by name pattern. Uses find command.",
        parameters=[
            ToolParameter(name="pattern", type="string", description="File name pattern to search (e.g., '*.py', 'report*', 'config.yaml')"),
            ToolParameter(name="directory", type="string", description="Directory to search in", required=False),
            ToolParameter(name="max_results", type="integer", description="Maximum results to return", required=False),
        ],
        function=file_manager.search_files,
        category="files",
    )

    registry.register(
        name="read_file",
        description="Read the contents of a text file",
        parameters=[
            ToolParameter(name="filepath", type="string", description="Path to the file to read"),
            ToolParameter(name="max_lines", type="integer", description="Maximum lines to read", required=False),
        ],
        function=file_manager.read_file,
        category="files",
    )

    registry.register(
        name="write_file",
        description="Write content to a file (creates or overwrites)",
        parameters=[
            ToolParameter(name="filepath", type="string", description="Path to write to"),
            ToolParameter(name="content", type="string", description="Content to write"),
        ],
        function=file_manager.write_file,
        category="files",
        dangerous=True,
    )

    registry.register(
        name="list_directory",
        description="List files and directories in a given path",
        parameters=[
            ToolParameter(name="path", type="string", description="Directory path to list (default: current directory)", required=False),
        ],
        function=file_manager.list_directory,
        category="files",
    )

    registry.register(
        name="create_directory",
        description="Create a new directory (including parent directories if needed)",
        parameters=[
            ToolParameter(name="path", type="string", description="Directory path to create"),
        ],
        function=file_manager.create_directory,
        category="files",
    )

    # ==========================================
    # 6. Screenshot
    # ==========================================
    registry.register(
        name="take_screenshot",
        description="Take a screenshot of the entire screen or a specific window",
        parameters=[
            ToolParameter(name="filename", type="string", description="Output filename (default: screenshot.png)", required=False),
            ToolParameter(name="window", type="string", description="Window name to capture (default: full screen)", required=False),
        ],
        function=screenshot.take_screenshot,
        category="system",
    )

    # ==========================================
    # 7. System Info
    # ==========================================
    registry.register(
        name="get_system_info",
        description="Get system information: CPU usage, RAM usage, disk space, battery status, uptime, etc.",
        parameters=[
            ToolParameter(
                name="info_type",
                type="string",
                description="Type of info to get",
                required=False,
                enum=["all", "cpu", "memory", "disk", "battery", "network", "uptime"],
            ),
        ],
        function=system_info.get_system_info,
        category="system",
    )

    # ==========================================
    # 8. Media Player Control
    # ==========================================
    registry.register(
        name="media_control",
        description="Control media playback (play, pause, next, previous, stop) using playerctl",
        parameters=[
            ToolParameter(
                name="action",
                type="string",
                description="Media action to perform",
                enum=["play", "pause", "play-pause", "next", "previous", "stop"],
            ),
        ],
        function=media_player.media_control,
        category="media",
    )

    registry.register(
        name="get_now_playing",
        description="Get information about the currently playing media (title, artist, album)",
        parameters=[],
        function=media_player.get_now_playing,
        category="media",
    )

    # ==========================================
    # 9. Clipboard
    # ==========================================
    registry.register(
        name="get_clipboard",
        description="Get the current clipboard content",
        parameters=[],
        function=clipboard.get_clipboard,
        category="system",
    )

    registry.register(
        name="set_clipboard",
        description="Copy text to the system clipboard",
        parameters=[
            ToolParameter(name="text", type="string", description="Text to copy to clipboard"),
        ],
        function=clipboard.set_clipboard,
        category="system",
    )

    # ==========================================
    # 10. Model Switching (Meta-tool)
    # ==========================================
    registry.register(
        name="switch_ai_model",
        description="Switch Victoria's AI brain to a different model. Available: gemini, gemini_pro, sarvam, local_fast, local_coder, openrouter_free",
        parameters=[
            ToolParameter(name="model_name", type="string", description="Name of the model to switch to"),
        ],
        function=lambda model_name: f"Model switch requested: {model_name}",  # Handled specially by router
        category="meta",
    )

    # ==========================================
    # 11. Custom Scripts
    # ==========================================
    registry.register(
        name="list_custom_scripts",
        description="List all available custom bash/python automation scripts in scripts/custom/",
        parameters=[],
        function=custom_scripts.list_custom_scripts,
        category="custom",
    )

    registry.register(
        name="run_custom_script",
        description="Execute a custom script located in scripts/custom/",
        parameters=[
            ToolParameter(name="script_name", type="string", description="Name of the script to execute (e.g. backup.sh)"),
            ToolParameter(name="args", type="string", description="Optional arguments to pass", required=False),
        ],
        function=custom_scripts.run_custom_script,
        category="custom",
        dangerous=True,
    )

    # ==========================================
    # 12. REA (Reverse Engineer Anything) Engine
    # ==========================================
    from victoria.rea.teardown import ReverseEngineerEngine
    from victoria.builder.code_agent import CodeBuilderAgent
    from victoria.builder.preview import LivePreviewServer

    rea_engine = ReverseEngineerEngine()
    code_builder = CodeBuilderAgent()
    preview_server = LivePreviewServer()

    def _rea_anything(target: str, target_type: str = "auto") -> str:
        report = rea_engine.teardown(target=target, target_type=target_type)
        return (
            f"✅ REA Teardown Complete for '{target}' (Type: {report['target_type']}) in {report['duration_seconds']}s.\n"
            f"📄 Full Markdown Report: {report['markdown_report_path']}\n"
            f"💾 Raw JSON Report: {report['json_report_path']}\n"
            f"Key Findings: {json.dumps(report['findings'])[:1000]}"
        )

    def _rea_website(url: str, deep_crawl: bool = True) -> str:
        report = rea_engine.teardown(target=url, target_type="website")
        endpoints = report['findings'].get('endpoints', [])
        return (
            f"✅ Website Reverse Engineered: '{url}'\n"
            f"- Discovered {len(endpoints)} API endpoints\n"
            f"- Tech Stack: {json.dumps(report['findings'].get('tech_stack', {}))}\n"
            f"- Report: {report['markdown_report_path']}"
        )

    def _rea_app(target: str) -> str:
        report = rea_engine.teardown(target=target, target_type="app")
        return (
            f"✅ App Reverse Engineered: '{target}' ({report['findings'].get('app_type')})\n"
            f"- Report: {report['markdown_report_path']}"
        )

    def _rea_db(target: str) -> str:
        report = rea_engine.teardown(target=target, target_type="database")
        return (
            f"✅ Database Reverse Engineered: '{target}'\n"
            f"- Tables: {len(report['findings'].get('tables', {}))}\n"
            f"- ERD & Models: {report['markdown_report_path']}"
        )

    def _rea_device(target: str = "all") -> str:
        report = rea_engine.teardown(target=target, target_type="device")
        return (
            f"✅ Device/Network Scan: '{target}'\n"
            f"- Summary: {report['reconstructed_code']}\n"
            f"- Report: {report['markdown_report_path']}"
        )

    registry.register(
        name="reverse_engineer_anything",
        description="Deeply reverse engineer any given target (website URL, app binary, .asar file, running process, database, USB/network device). Generates architecture teardown reports and reconstructed code.",
        parameters=[
            ToolParameter(name="target", type="string", description="The target to reverse engineer (URL, file path, PID, database path, or device IP/category)"),
            ToolParameter(name="target_type", type="string", description="Target type: 'auto', 'website', 'app', 'database', 'device'", required=False),
        ],
        function=_rea_anything,
        category="rea",
    )

    registry.register(
        name="reverse_engineer_website",
        description="Reverse engineer a website or web app: extracts API endpoints, tech stack, DOM structure, CSS tokens, and generates Python API SDK client code.",
        parameters=[
            ToolParameter(name="url", type="string", description="Target website URL"),
            ToolParameter(name="deep_crawl", type="boolean", description="Whether to deep-scan linked JS bundles for hidden APIs", required=False),
        ],
        function=_rea_website,
        category="rea",
    )

    registry.register(
        name="reverse_engineer_app",
        description="Reverse engineer an application: extracts Electron ASAR files, ELF binary symbols, strings, dependencies, or inspects a live running process by PID/name.",
        parameters=[
            ToolParameter(name="target", type="string", description="File path to .asar, binary, or process PID / application name"),
        ],
        function=_rea_app,
        category="rea",
    )

    registry.register(
        name="reverse_engineer_database",
        description="Reverse engineer a database: extracts tables, columns, foreign keys, row counts, generates Mermaid ERD diagrams and SQLAlchemy Python models.",
        parameters=[
            ToolParameter(name="target", type="string", description="Path to .sqlite/.db file or connection URI (postgres://, mysql://, redis://)"),
        ],
        function=_rea_db,
        category="rea",
    )

    registry.register(
        name="reverse_engineer_device",
        description="Reverse engineer devices and hardware: scans USB devices, PCI buses, Bluetooth peripherals, LAN hosts, or scans open ports on a network device.",
        parameters=[
            ToolParameter(name="target", type="string", description="'all', 'usb', 'pci', 'bluetooth', 'lan', or specific IP address (e.g. 192.168.1.1)", required=False),
        ],
        function=_rea_device,
        category="rea",
    )

    # ==========================================
    # 13. Auto-Builder & Preview
    # ==========================================
    registry.register(
        name="build_mock_server",
        description="Generate a runnable FastAPI mock server mimicking the API endpoints discovered in a teardown report",
        parameters=[
            ToolParameter(name="teardown_report_path", type="string", description="Path to the .json teardown report file"),
        ],
        function=lambda teardown_report_path: f"Mock server created at: {code_builder.build_mock_server_from_teardown(teardown_report_path)}",
        category="builder",
    )

    registry.register(
        name="build_frontend_clone",
        description="Generate an HTML/CSS frontend clone based on the design tokens and layout discovered in a teardown report",
        parameters=[
            ToolParameter(name="teardown_report_path", type="string", description="Path to the .json teardown report file"),
        ],
        function=lambda teardown_report_path: f"Frontend clone created at: {code_builder.build_frontend_clone(teardown_report_path)}",
        category="builder",
    )

    registry.register(
        name="start_preview_server",
        description="Start a local web server to preview generated frontend clones or mock APIs",
        parameters=[
            ToolParameter(name="directory", type="string", description="Directory to serve on localhost"),
            ToolParameter(name="port", type="integer", description="Port number (default: 5173)", required=False),
        ],
        function=lambda directory, port=5173: preview_server.start(directory, port),
        category="builder",
    )

    # ==========================================
    # 14. LeanToken (Token Optimizer & Code Intelligence)
    # ==========================================
    registry.register(
        name="leantoken_get_context",
        description="Retrieve ranked code snippets strictly bounded by a token budget to save AI LLM tokens (powered by LeanToken)",
        parameters=[
            ToolParameter(name="task", type="string", description="Description of the task or feature to get context for"),
            ToolParameter(name="budget", type="integer", description="Maximum token budget (default: 2000)", required=False),
        ],
        function=lambda task, budget=2000: leantoken_tool.get_lean_context(task, budget),
        category="leantoken",
    )

    registry.register(
        name="leantoken_search",
        description="Search symbols, functions, or terms across the codebase with minimal token usage",
        parameters=[
            ToolParameter(name="query", type="string", description="Symbol, function name, or search query"),
        ],
        function=leantoken_tool.lean_search,
        category="leantoken",
    )

    registry.register(
        name="leantoken_outline",
        description="Get structural outline of a file (classes, functions, methods) without consuming tokens reading the full file body",
        parameters=[
            ToolParameter(name="file_path", type="string", description="Relative or absolute path to the file"),
        ],
        function=leantoken_tool.lean_outline,
        category="leantoken",
    )

    registry.register(
        name="leantoken_read_range",
        description="Read an exact bounded line range from a file (saving tokens compared to reading the whole file)",
        parameters=[
            ToolParameter(name="file_path", type="string", description="File path to read from"),
            ToolParameter(name="start_line", type="integer", description="1-indexed start line"),
            ToolParameter(name="end_line", type="integer", description="1-indexed end line"),
        ],
        function=leantoken_tool.lean_read_range,
        category="leantoken",
    )

    registry.register(
        name="leantoken_index_repo",
        description="Index or update the codebase index in LeanToken's local cache for instant retrieval",
        parameters=[],
        function=leantoken_tool.index_repository,
        category="leantoken",
    )

    registry.register(
        name="leantoken_savings",
        description="Check LeanToken source compression and token accounting report",
        parameters=[],
        function=leantoken_tool.get_token_savings,
        category="leantoken",
    )

    # ==========================================
    # 15. Persona & Digital Twin Engine
    # ==========================================
    registry.register(
        name="view_owner_persona",
        description="View the current Owner Persona Dossier & Digital Twin profile (what Victoria knows about the owner's likes, dislikes, intentions, and habits)",
        parameters=[],
        function=persona_tool.view_owner_persona,
        category="persona",
    )

    registry.register(
        name="remember_owner_preference",
        description="Explicitly record a new preference, dislike, goal/intention, or tech habit about the owner to evolve Victoria's digital twin alignment",
        parameters=[
            ToolParameter(name="category", type="string", description="Category: 'like' (पसंद), 'dislike' (नापसंद), 'goal' (इरादा/लक्ष्य), or 'tech' (तकनीक)"),
            ToolParameter(name="detail", type="string", description="The specific fact or preference to remember"),
        ],
        function=persona_tool.remember_owner_preference,
        category="persona",
    )

    registry.register(
        name="get_owner_intentions",
        description="Get the list of active missions, goals, and long-term intentions of the owner",
        parameters=[],
        function=persona_tool.get_owner_intentions,
        category="persona",
    )

    # ==========================================
    # 16. Local Offline Owner Memory Vault
    # ==========================================
    registry.register(
        name="save_owner_memory",
        description="Save a personal fact, preference, intention, project, event, or note about the owner into 100% local offline SQLite storage",
        parameters=[
            ToolParameter(name="content", type="string", description="The memory content to store"),
            ToolParameter(name="category", type="string", description="Category: 'fact', 'preference', 'intention', 'project', 'event', 'note' (default: 'fact')", required=False),
            ToolParameter(name="title", type="string", description="Short title or summary (optional)", required=False),
            ToolParameter(name="tags", type="string", description="Comma-separated keywords/tags (optional)", required=False),
            ToolParameter(name="importance", type="integer", description="Importance rating from 1 to 5 (default: 3)", required=False),
        ],
        function=lambda content, category="fact", title="", tags="", importance=3: owner_memory_tool.save_owner_memory(content, category, title, tags, importance),
        category="memory",
    )

    registry.register(
        name="search_owner_memory",
        description="Search local offline memories about the owner using SQLite FTS5 full-text search (works completely offline with zero internet)",
        parameters=[
            ToolParameter(name="query", type="string", description="Search query or keyword in Hindi or English"),
            ToolParameter(name="category", type="string", description="Filter by category (optional)", required=False),
        ],
        function=lambda query, category="": owner_memory_tool.search_owner_memory(query, category),
        category="memory",
    )

    registry.register(
        name="list_owner_memories",
        description="List stored offline memories of the owner, ordered by importance and recency",
        parameters=[
            ToolParameter(name="category", type="string", description="Filter by category (optional)", required=False),
            ToolParameter(name="limit", type="integer", description="Maximum number of memories to return (default: 10)", required=False),
        ],
        function=lambda category="", limit=10: owner_memory_tool.list_owner_memories(category, limit),
        category="memory",
    )

    registry.register(
        name="delete_owner_memory",
        description="Delete a specific local offline memory by its ID",
        parameters=[
            ToolParameter(name="memory_id", type="integer", description="ID of the memory to delete"),
        ],
        function=owner_memory_tool.delete_owner_memory,
        category="memory",
    )

    # ==========================================
    # 17. Experiential Learning & Self-Evolution
    # ==========================================
    from victoria.tools import experience_tool

    registry.register(
        name="remember_learned_rule",
        description="Remember a new rule, correction, or preferred workflow learned from interacting with the owner so future executions are better",
        parameters=[
            ToolParameter(name="rule", type="string", description="The rule or behavior to remember (e.g. 'Always save screenshots to /home/hariom/Pictures')"),
            ToolParameter(name="trigger", type="string", description="Keywords or topic triggering this rule (optional)", required=False),
            ToolParameter(name="rule_type", type="string", description="'correction', 'preference', 'shortcut', or 'guardrail'", required=False),
        ],
        function=lambda rule, trigger="", rule_type="correction": experience_tool.remember_learned_rule(rule, trigger, rule_type),
        category="experience",
    )

    registry.register(
        name="view_learned_skills",
        description="View Victoria's learned task recipes, past lessons, and current assistant evolution level",
        parameters=[],
        function=experience_tool.view_learned_skills,
        category="experience",
    )

    console.print(f"[green]✅ {len(registry.list_tools())} tools registered[/green]")
    return registry
