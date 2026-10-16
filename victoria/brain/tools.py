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
        self._mcp_clients: list = []       # live MCP server clients, kept alive here

    def register(
        self,
        name: str,
        description: str,
        parameters: list[ToolParameter],
        function: Callable,
        category: str = "general",
        dangerous: bool = False,
        raw_schema: Optional[dict] = None,
    ):
        """Register a tool."""
        self._tools[name] = {
            "definition": ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                category=category,
                dangerous=dangerous,
                raw_schema=raw_schema,
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
        daily_work_tool,
        media_vision_tool,
        weather_tool,
    )

    registry.register(
        name="get_weather",
        description="Get current real-time weather information and forecast for any city or location",
        parameters=[
            ToolParameter(name="city", type="string", description="City name (e.g. Varanasi, Delhi, Mumbai)", required=False),
        ],
        function=weather_tool.get_weather,
        category="system",
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
        description=(
            "Execute a safe Linux terminal/shell command and return output. "
            "STRICT SECURITY LOCK: Operating system reboot/shutdown and file deletion (rm/remove/unlink) "
            "are permanently locked by security policy and will be rejected automatically. "
            "Never use this tool to reboot the system or delete files."
        ),
        parameters=[
            ToolParameter(name="command", type="string", description="The shell command to execute (OS reboot and file removal are permanently blocked)"),
            ToolParameter(name="timeout", type="integer", description="Timeout in seconds", required=False),
            ToolParameter(name="confirmed", type="boolean", description="Confirmation flag for dangerous operations. NOTE: OS reboot and file deletion are permanently locked and cannot be executed even if confirmed.", required=False),
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
        description="Take and save a screenshot ONLY when Hariom explicitly asks to take/save a screenshot (e.g. 'take a screenshot', 'screenshot lo'). Never call this automatically or repeatedly.",
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

    registry.register(
        name="create_offline_skill_script",
        description="Create a new offline executable bash or python automation script in scripts/custom/. Enables Victoria to learn and store offline skills that run without internet.",
        parameters=[
            ToolParameter(name="script_name", type="string", description="Script file name (e.g. system_cleanup.sh, disk_health.py)"),
            ToolParameter(name="content", type="string", description="Full script content including shebang (#!/bin/bash or #!/usr/bin/env python3)"),
            ToolParameter(name="description", type="string", description="What this offline script accomplishes", required=False),
        ],
        function=custom_scripts.create_custom_script,
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
    # 16b. Daily Work Journal & Continuity Tools
    # ==========================================
    registry.register(
        name="log_daily_task",
        description="Log a task, activity, or milestone into Hariom's persistent daily work journal (stored locally in SQLite and exported to Markdown)",
        parameters=[
            ToolParameter(name="title", type="string", description="Short descriptive title of the task"),
            ToolParameter(name="description", type="string", description="Detailed description of what was completed or attempted"),
            ToolParameter(name="status", type="string", description="'completed', 'in_progress', 'pending', or 'paused'", required=False),
            ToolParameter(name="tools_used", type="string", description="Names of tools used", required=False),
            ToolParameter(name="next_steps", type="string", description="Recommended next steps or follow-ups", required=False),
            ToolParameter(name="project", type="string", description="Project name (default: PROJECT VICTORIA)", required=False),
        ],
        function=lambda title, description, status="completed", tools_used="", next_steps="", project="PROJECT VICTORIA": daily_work_tool.log_daily_task(title, description, status, tools_used, next_steps, project),
        category="memory",
    )

    registry.register(
        name="get_daily_work_journal",
        description="Retrieve the complete daily work journal and activity log for today or a specific date",
        parameters=[
            ToolParameter(name="date", type="string", description="Date in YYYY-MM-DD format (leave blank for today)", required=False),
        ],
        function=lambda date="": daily_work_tool.get_daily_work_journal(date),
        category="memory",
    )

    registry.register(
        name="get_last_work_checkpoint",
        description="Check where work was left off, current project state, and next steps to resume exactly where work stopped",
        parameters=[],
        function=daily_work_tool.get_last_work_checkpoint,
        category="memory",
    )

    registry.register(
        name="save_work_checkpoint",
        description="Save or update the 'Where We Left Off' checkpoint with current progress and next planned steps",
        parameters=[
            ToolParameter(name="last_task", type="string", description="Title of the current or last task"),
            ToolParameter(name="where_we_left_off", type="string", description="Clear description of the exact state where work is stopping"),
            ToolParameter(name="next_planned_steps", type="string", description="What to do next when resuming work", required=False),
            ToolParameter(name="project", type="string", description="Project name", required=False),
            ToolParameter(name="active_files", type="string", description="Relevant files or components", required=False),
        ],
        function=lambda last_task, where_we_left_off, next_planned_steps="", project="PROJECT VICTORIA", active_files="": daily_work_tool.save_work_checkpoint(last_task, where_we_left_off, next_planned_steps, project, active_files),
        category="memory",
    )

    registry.register(
        name="query_work_by_date_time",
        description="Find out what was done on a specific date and time based on natural queries (e.g. '16 तारीख को 2:30 बजे क्या किया था?', 'आज 3 बजे क्या हुआ था?')",
        parameters=[
            ToolParameter(name="query", type="string", description="The user query or question about the past date/time"),
            ToolParameter(name="date", type="string", description="Optional date in YYYY-MM-DD format", required=False),
            ToolParameter(name="time", type="string", description="Optional time in HH:MM format", required=False),
        ],
        function=lambda query, date="", time="": daily_work_tool.query_work_by_date_time(query, date, time),
        category="memory",
    )

    # ==========================================
    # 16c. Multimodal Vision & Video Analysis
    # ==========================================
    registry.register(
        name="analyze_image",
        description="Visually analyze any image, photo, UI mockup, diagram, or error screenshot. Explains content, detects objects, reads text/code, and answers questions",
        parameters=[
            ToolParameter(name="image_path", type="string", description="Absolute or relative file path to the image"),
            ToolParameter(name="question", type="string", description="Specific question or aspect to explain about the image", required=False),
        ],
        function=lambda image_path, question="": media_vision_tool.analyze_image(image_path, question),
        category="vision",
    )

    registry.register(
        name="analyze_video",
        description="Visually analyze any video file (MP4, MKV, AVI, WEBM, MOV). Samples keyframes, generates visual montage, and explains scenes, actions, timeline, and objects",
        parameters=[
            ToolParameter(name="video_path", type="string", description="Absolute or relative file path to the video"),
            ToolParameter(name="question", type="string", description="Specific question about the video", required=False),
            ToolParameter(name="max_frames", type="integer", description="Number of keyframes to sample (default: 6, max: 12)", required=False),
        ],
        function=lambda video_path, question="", max_frames=6: media_vision_tool.analyze_video(video_path, question, max_frames),
        category="vision",
    )

    registry.register(
        name="analyze_current_screen",
        description="Capture a live screenshot of Hariom's screen and explain what's visible ONLY when Hariom explicitly asks what is on screen or to inspect the screen (e.g. 'screen par kya chal raha hai', 'look at my screen', 'meri screen dekho'). Never call this continuously or unsolicited.",
        parameters=[
            ToolParameter(name="question", type="string", description="Specific question about the screen (e.g. 'explain this error', 'what is in this window')", required=False),
        ],
        function=lambda question="": media_vision_tool.analyze_current_screen(question),
        category="vision",
    )

    from victoria.tools import desktop_inspector
    registry.register(
        name="get_desktop_screen_overview",
        description="Inspect active desktop GUI applications, open windows, media playback, and workspace project state without taking screenshots or writing files to disk. Fast, lightweight, and zero-disk overhead.",
        parameters=[],
        function=desktop_inspector.get_desktop_screen_overview,
        category="system",
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

    # ==========================================
    # 18. Self-Configuration & Code Self-Evolution
    # ==========================================
    def _tool_update_setting(setting_path: str, value: str) -> str:
        from victoria.config import get_config
        cfg = get_config()
        val = value
        if isinstance(val, str):
            if val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            else:
                try:
                    val = float(val) if "." in val else int(val)
                except ValueError:
                    pass
        cfg.set(setting_path, val, persist=True)
        return f"सेटिंग सफलतापूर्वक अपडेट कर दी गई: '{setting_path}' = {val}"

    def _tool_get_settings(section: str = "") -> str:
        from victoria.config import get_config
        import yaml
        cfg = get_config()
        data = cfg.get(section) if section else cfg._raw
        return yaml.dump(data, default_flow_style=False)

    def _tool_modify_code(relative_filepath: str, new_content: str, explanation: str) -> str:
        from victoria.config import PROJECT_ROOT
        import py_compile
        target = (PROJECT_ROOT / relative_filepath).resolve()
        if not str(target).startswith(str(PROJECT_ROOT)):
            return "त्रुटि: प्रोजेक्ट डायरेक्टरी से बाहर की फाइल्स संशोधित नहीं की जा सकतीं।"
        backup = target.with_suffix(target.suffix + ".bak")
        if target.exists():
            backup.write_bytes(target.read_bytes())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_content, encoding="utf-8")
        if target.suffix == ".py":
            try:
                py_compile.compile(str(target), doraise=True)
            except py_compile.PyCompileError as pe:
                if backup.exists():
                    target.write_bytes(backup.read_bytes())
                return f"कोड सिंटेक्स एरर: {pe}. पिछला बैकअप पुनर्स्थापित कर दिया गया।"
        return f"सफलतापूर्वक कोड अपडेट किया: '{relative_filepath}' ({explanation}). सिंटेक्स सत्यापित है।"

    registry.register(
        name="update_victoria_setting",
        description="Update Victoria's configuration settings (e.g. 'voice.wake_phrase', 'voice.tts.edge_tts.voice', 'voice.wake_word.sensitivity', 'brain.active_model', etc.) and persist to victoria.yaml",
        parameters=[
            ToolParameter(name="setting_path", type="string", description="Dot-separated path in victoria.yaml (e.g. 'voice.wake_phrase', 'voice.speaker_verify.threshold')"),
            ToolParameter(name="value", type="string", description="New value to set (string, number, or boolean)"),
        ],
        function=_tool_update_setting,
        category="self_evolution",
    )

    registry.register(
        name="get_victoria_settings",
        description="Inspect Victoria's active configuration settings from victoria.yaml",
        parameters=[
            ToolParameter(name="section", type="string", description="Optional section like 'voice', 'brain', 'system'", required=False),
        ],
        function=_tool_get_settings,
        category="self_evolution",
    )

    registry.register(
        name="modify_victoria_code",
        description="Modify or patch Victoria's own Python source code files to fix bugs, add capabilities, or improve behavior based on owner feedback. Automatically creates backup and verifies Python syntax.",
        parameters=[
            ToolParameter(name="relative_filepath", type="string", description="Relative path in Project Victoria (e.g. 'victoria/voice/voice_model_manager.py')"),
            ToolParameter(name="new_content", type="string", description="Full updated file content"),
            ToolParameter(name="explanation", type="string", description="Why this code is being changed and what bug/feature it addresses"),
        ],
        function=_tool_modify_code,
        category="self_evolution",
        dangerous=True,
    )

    def _tool_switch_voice(voice_name: str) -> str:
        from victoria.voice.tts import TextToSpeech
        tts = TextToSpeech()
        v_key, v_name = tts.set_voice(voice_name, persist=True)
        return f"Victoria voice successfully changed to: {v_name}"

    registry.register(
        name="switch_assistant_voice",
        description="Switch Victoria's speaking voice. Available female voices: 'swara' (Indian sweet Hindi), 'ava' (Jarvis-style modern multilingual AI), 'emma' (soft & clear AI), 'seraphina' (royal AI).",
        parameters=[
            ToolParameter(name="voice_name", type="string", description="Name or key of the voice: 'swara', 'ava', 'emma', 'seraphina'"),
        ],
        function=_tool_switch_voice,
        category="self_evolution",
    )

    def _tool_demo_voices() -> str:
        from victoria.voice.tts import TextToSpeech
        tts = TextToSpeech()
        return tts.demo_all_voices()

    registry.register(
        name="demo_all_voices",
        description="Showcase and play a live voice sample in each available female AI voice (Swara, Ava, Emma, Seraphina) one after the other.",
        parameters=[],
        function=_tool_demo_voices,
        category="voice",
    )

    def _tool_lock_system() -> str:
        from victoria.tools.system_lock import lock_system
        return lock_system()

    registry.register(
        name="lock_system_screen",
        description="Lock the Linux desktop session screen immediately.",
        parameters=[],
        function=_tool_lock_system,
        category="system",
    )

    def _tool_unlock_system() -> str:
        from victoria.tools.system_lock import unlock_system_by_voice
        res = unlock_system_by_voice(similarity=0.90)
        return res.get("message", "स्क्रीन अनलॉक कर दी गई है।")

    registry.register(
        name="unlock_system_screen",
        description="Unlock the Linux desktop session screen using voice biometrics.",
        parameters=[],
        function=_tool_unlock_system,
        category="system",
    )

    def _tool_stop_speech() -> str:
        from victoria.voice.tts import TextToSpeech
        tts = TextToSpeech()
        tts.stop()
        return "Victoria speech playback stopped immediately."

    registry.register(
        name="stop_assistant_speech",
        description="Immediately halt or interrupt Victoria's speech audio playback (< 20ms).",
        parameters=[],
        function=_tool_stop_speech,
        category="voice",
    )

    # ==========================================
    # 17. Autonomous Skill R&D & Internet Search
    # ==========================================
    def _tool_search_internet(query: str, max_results: int = 5) -> str:
        from victoria.brain.skill_rnd import get_skill_rnd_engine
        engine = get_skill_rnd_engine()
        results = engine.search_internet(query, max_results=max_results)
        if not results:
            return f"No internet search results found for: {query}"
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(f"{i}. {r['title']}\n   Snippet: {r['snippet']}\n   URL: {r['url']}")
        return "\n\n".join(formatted)

    registry.register(
        name="search_internet",
        description="Search the live internet for answers, technical documentation, Linux commands, APIs, tutorials, and latest news using DuckDuckGo and Wikipedia.",
        parameters=[
            ToolParameter(name="query", type="string", description="The search query"),
            ToolParameter(name="max_results", type="integer", description="Maximum number of search results (default 5)", required=False),
        ],
        function=_tool_search_internet,
        category="research",
    )

    def _tool_acquire_skill(topic: str, description: str = "") -> str:
        from victoria.brain.skill_rnd import get_skill_rnd_engine
        engine = get_skill_rnd_engine()
        res = engine.acquire_skill(topic=topic, user_description=description)
        return json.dumps(res, ensure_ascii=False)

    registry.register(
        name="research_and_acquire_skill",
        description="Autonomous R&D: Research a requested topic on the internet, synthesize a complete offline skill module, save python automation script and knowledge docs, and register it into Victoria's brain.",
        parameters=[
            ToolParameter(name="topic", type="string", description="Skill or capability topic to research and learn (e.g. 'stock market technical analysis', 'docker container monitoring', 'youtube video downloader', 'crypto price tracker')"),
            ToolParameter(name="description", type="string", description="Optional additional user requirements or specific instructions", required=False),
        ],
        function=_tool_acquire_skill,
        category="self_evolution",
        dangerous=True,
    )

    def _tool_list_skills() -> str:
        from victoria.brain.skill_rnd import get_skill_rnd_engine
        engine = get_skill_rnd_engine()
        skills = engine.list_skills()
        if not skills:
            return "No custom autonomous skills acquired yet."
        formatted = []
        for s in skills:
            formatted.append(f"- **{s['title']}** (`{s['slug']}`): {s['description']}\n  Script: `{s['script_path']}`")
        return "\n".join(formatted)

    registry.register(
        name="list_learned_skills",
        description="List all skills and capabilities that Victoria has autonomously researched, learned, and stored in her local knowledge and script vault.",
        parameters=[],
        function=_tool_list_skills,
        category="self_evolution",
    )

    # ==========================================
    # 18. Mouse & Keyboard Hardware/OS Automation
    # ==========================================
    from victoria.tools import input_control

    registry.register(
        name="mouse_click",
        description="Click the mouse cursor at specific (x, y) coordinates or at current position. Supports left, right, or middle click, and single or double clicks.",
        parameters=[
            ToolParameter(name="x", type="integer", description="X coordinate on screen (optional, clicks at current position if omitted)", required=False),
            ToolParameter(name="y", type="integer", description="Y coordinate on screen (optional, clicks at current position if omitted)", required=False),
            ToolParameter(name="button", type="string", description="Mouse button: 'left', 'right', or 'middle' (default 'left')", required=False),
            ToolParameter(name="clicks", type="integer", description="Number of clicks: 1 for single click, 2 for double click (default 1)", required=False),
        ],
        function=input_control.mouse_click,
        category="input_automation",
    )

    registry.register(
        name="mouse_move",
        description="Move the mouse pointer to (x, y) pixel coordinates on the screen.",
        parameters=[
            ToolParameter(name="x", type="integer", description="Target X coordinate (0 to screen_width)"),
            ToolParameter(name="y", type="integer", description="Target Y coordinate (0 to screen_height)"),
            ToolParameter(name="smooth", type="boolean", description="If True, moves smoothly with human-like motion (default True)", required=False),
        ],
        function=input_control.mouse_move,
        category="input_automation",
    )

    registry.register(
        name="mouse_drag",
        description="Click and drag from (start_x, start_y) to (end_x, end_y). Useful for selecting text, dragging windows, sliders, or moving desktop icons.",
        parameters=[
            ToolParameter(name="start_x", type="integer", description="Starting X coordinate"),
            ToolParameter(name="start_y", type="integer", description="Starting Y coordinate"),
            ToolParameter(name="end_x", type="integer", description="Ending X coordinate"),
            ToolParameter(name="end_y", type="integer", description="Ending Y coordinate"),
            ToolParameter(name="button", type="string", description="Button to hold down: 'left' or 'right' (default 'left')", required=False),
        ],
        function=input_control.mouse_drag,
        category="input_automation",
    )

    registry.register(
        name="mouse_scroll",
        description="Scroll the mouse wheel up or down by a given number of steps.",
        parameters=[
            ToolParameter(name="clicks", type="integer", description="Number of scroll steps (default 3)", required=False),
            ToolParameter(name="direction", type="string", description="Scroll direction: 'up' or 'down' (default 'down')", required=False),
        ],
        function=input_control.mouse_scroll,
        category="input_automation",
    )

    registry.register(
        name="get_mouse_position",
        description="Get current mouse cursor coordinates (x, y) and screen dimensions (width, height).",
        parameters=[],
        function=input_control.get_mouse_position,
        category="input_automation",
    )

    registry.register(
        name="keyboard_type",
        description="Type text string into the currently focused window or active text field.",
        parameters=[
            ToolParameter(name="text", type="string", description="The text string to type out"),
            ToolParameter(name="delay", type="number", description="Delay between keystrokes in seconds (default 0.02)", required=False),
        ],
        function=input_control.keyboard_type,
        category="input_automation",
    )

    registry.register(
        name="keyboard_hotkey",
        description="Trigger keyboard shortcut combinations (e.g. 'ctrl+c', 'ctrl+v', 'alt+tab', 'super', 'ctrl+alt+t', 'ctrl+w', 'ctrl+t').",
        parameters=[
            ToolParameter(name="hotkey", type="string", description="Hotkey string combination (e.g. 'ctrl+c', 'alt+tab', 'super', 'ctrl+alt+t')"),
        ],
        function=input_control.keyboard_hotkey,
        category="input_automation",
    )

    registry.register(
        name="keyboard_press",
        description="Press a single special keyboard key (e.g. 'Enter', 'Escape', 'BackSpace', 'Tab', 'Space', 'Up', 'Down', 'Left', 'Right', 'Home', 'End').",
        parameters=[
            ToolParameter(name="key", type="string", description="Key name to press (e.g. 'Enter', 'Escape', 'BackSpace', 'Tab', 'Space')"),
        ],
        function=input_control.keyboard_press,
        category="input_automation",
    )

    # ==========================================
    # 18. MCP Servers (e.g. morluto/rea reverse-engineering tools)
    # ==========================================
    try:
        from victoria.config import get_config
        from victoria.brain.mcp_bridge import load_mcp_servers
        load_mcp_servers(registry, get_config().get("mcp", {}))
    except Exception as e:  # noqa: BLE001 - MCP is optional; never break startup
        console.print(f"[yellow]⚠️ MCP bridge skipped: {e}[/yellow]")

    console.print(f"[green]✅ {len(registry.list_tools())} tools registered[/green]")
    return registry
