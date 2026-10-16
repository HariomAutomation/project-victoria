"""
Victoria - REA Master Teardown Engine
Orchestrates reverse engineering across Websites, Apps/Binaries, Databases, and Devices.
Produces structured teardown reports and reconstructed code specifications.
"""

import json
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional
from rich.console import Console

from victoria.config import PROJECT_ROOT
from victoria.rea.web_inspector import WebInspector
from victoria.rea.app_inspector import AppInspector
from victoria.rea.db_inspector import DBInspector
from victoria.rea.device_inspector import DeviceInspector

console = Console()


class ReverseEngineerEngine:
    """
    Reverse Engineer Anything (REA) Engine.
    Handles inspection and reconstruction of:
      1. Websites and Web Applications
      2. Desktop Apps, Binaries, and Running Processes
      3. Databases (SQLite, PostgreSQL, MySQL, Redis)
      4. Devices, Hardware, and Local Network Hosts
    """

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "data" / "teardowns"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.web_inspector = WebInspector()
        self.app_inspector = AppInspector(output_dir=str(self.output_dir / "extracted_apps"))
        self.db_inspector = DBInspector()
        self.device_inspector = DeviceInspector()

    def teardown(self, target: str, target_type: str = "auto") -> dict[str, Any]:
        """
        Reverse engineer any target.

        Args:
            target: The target to reverse engineer (URL, file path, PID, db path, device/IP)
            target_type: "auto", "website", "app", "database", "device"

        Returns:
            Dictionary containing teardown findings and report file paths.
        """
        start_time = time.time()
        detected_type = self._detect_target_type(target) if target_type == "auto" else target_type.lower()
        console.print(f"[bold cyan]🚀 Starting REA Teardown on '{target}' (Type: {detected_type})[/bold cyan]")

        slug = re.sub(r'[^a-zA-Z0-9_-]', '_', target.replace('https://', '').replace('http://', ''))[:40].strip('_')
        timestamp = int(start_time)
        report_base = f"{slug}_{timestamp}"

        report_data: dict[str, Any] = {
            "target": target,
            "target_type": detected_type,
            "timestamp": timestamp,
            "duration_seconds": 0.0,
            "findings": {},
            "reconstructed_code": "",
            "markdown_report_path": "",
            "json_report_path": "",
        }

        # Dispatch based on detected type
        if detected_type == "website":
            web_res = self.web_inspector.inspect(target)
            report_data["findings"] = asdict(web_res)
            report_data["reconstructed_code"] = self.web_inspector.generate_api_client_code(web_res)
            md_content = self._build_web_markdown(web_res, report_data["reconstructed_code"])

        elif detected_type == "app":
            app_res = self.app_inspector.inspect(target)
            report_data["findings"] = asdict(app_res)
            report_data["reconstructed_code"] = app_res.reconstructed_skeleton
            md_content = self._build_app_markdown(app_res)

        elif detected_type == "database":
            db_res = self.db_inspector.inspect(target)
            report_data["findings"] = asdict(db_res)
            report_data["reconstructed_code"] = db_res.sqlalchemy_models
            md_content = self._build_db_markdown(db_res)

        elif detected_type == "device":
            dev_res = self.device_inspector.inspect(target)
            report_data["findings"] = asdict(dev_res)
            report_data["reconstructed_code"] = dev_res.reconstructed_profile
            md_content = self._build_device_markdown(dev_res)

        else:
            md_content = f"# Teardown for {target}\n\nCould not automatically determine target type."
            report_data["findings"] = {"error": "Unsupported target type"}

        report_data["duration_seconds"] = round(time.time() - start_time, 2)

        # Save Markdown Report
        md_path = self.output_dir / f"{report_base}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        report_data["markdown_report_path"] = str(md_path)

        # Save JSON Report
        json_path = self.output_dir / f"{report_base}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        report_data["json_report_path"] = str(json_path)

        console.print(f"[bold green]✨ REA Teardown Complete in {report_data['duration_seconds']}s![/bold green]")
        console.print(f"[green]📄 Report saved to: {md_path}[/green]")

        return report_data

    def _detect_target_type(self, target: str) -> str:
        """Heuristically identify the category of target."""
        t = target.strip().lower()

        # 1. Website
        if t.startswith(("http://", "https://")) or t.endswith((".com", ".org", ".io", ".dev", ".net", ".in", ".ai")):
            return "website"

        # 2. Database
        if t.endswith((".db", ".sqlite", ".sqlite3")) or t.startswith(("postgres://", "postgresql://", "mysql://", "redis://")):
            return "database"

        # 3. Device / Network
        if t in ["usb", "pci", "bluetooth", "lan", "all"] or t.startswith(("usb:", "pci:", "bt:", "ip:")) or re.match(r'^(?:\d{1,3}\.){3}\d{1,3}$', t):
            return "device"

        # 4. App / Binary (ELF binary, .asar, .apk, .py, PID, or command name)
        return "app"

    # =========================================================================
    # Markdown Report Builders
    # =========================================================================

    def _build_web_markdown(self, res: Any, code: str) -> str:
        lines = [
            f"# 🌐 REA Teardown Report: {res.target_url}",
            f"**Title:** {res.title} | **HTTP Status:** {res.status_code}\n",
            "## 🛠️ Detected Tech Stack",
        ]
        for category, items in res.tech_stack.items():
            if items:
                lines.append(f"- **{category.replace('_', ' ').title()}:** {', '.join(items)}")

        lines.extend([
            "\n## 🔗 Discovered API Endpoints & Routes",
            f"Total Endpoints Found: `{len(res.endpoints)}`\n",
        ])
        for ep in res.endpoints[:25]:
            lines.append(f"- `[{ep['method']}]` `{ep['url']}` ({ep['category']})")

        if res.websocket_urls:
            lines.extend(["\n### ⚡ WebSocket Endpoints", *[f"- `{w}`" for w in res.websocket_urls]])

        if res.potential_secrets:
            lines.extend(["\n### 🔑 Exposed Tokens / Secrets", *[f"- {s}" for s in res.potential_secrets]])

        if code:
            lines.extend([
                "\n## 💻 Reconstructed API Client SDK",
                "```python",
                code,
                "```",
            ])

        return "\n".join(lines)

    def _build_app_markdown(self, res: Any) -> str:
        lines = [
            f"# 📦 REA Teardown Report: {res.target}",
            f"**Application Type:** `{res.app_type}` | **Architecture:** `{res.architecture or 'N/A'}`\n",
            f"**Entry Point:** `{res.entry_point or 'N/A'}`\n",
            "## 📚 Dependencies & Shared Libraries",
            *[f"- `{d}`" for d in res.dependencies[:20]],
        ]

        if res.ipc_channels:
            lines.extend([
                "\n## ⚡ IPC Communication Channels",
                *[f"- `[{ipc['direction']}]` `{ipc['channel']}` ({ipc.get('file', '')})" for ipc in res.ipc_channels[:25]],
            ])

        if res.exported_functions:
            lines.extend([
                "\n## 📤 Exported Functions (Top 20)",
                *[f"- `{fn}`" for fn in res.exported_functions[:20]],
            ])

        if res.extracted_strings:
            lines.append("\n## 🔍 Extracted Strings")
            for cat, strs in res.extracted_strings.items():
                if strs:
                    lines.append(f"### {cat.title()}")
                    lines.extend([f"- `{s}`" for s in strs[:10]])

        if res.reconstructed_skeleton:
            lines.extend([
                "\n## 💻 Reconstructed Skeleton Code",
                "```javascript",
                res.reconstructed_skeleton,
                "```",
            ])

        return "\n".join(lines)

    def _build_db_markdown(self, res: Any) -> str:
        lines = [
            f"# 🗄️ REA Teardown Report: {res.target}",
            f"**Database Engine:** `{res.db_type}` | **Total Tables:** `{res.total_tables}`\n",
        ]

        if res.mermaid_erd:
            lines.extend([
                "## 📊 Entity Relationship Diagram (ERD)",
                "```mermaid",
                res.mermaid_erd,
                "```\n",
            ])

        lines.append("## 📋 Tables & Schema Definitions")
        for t_name, schema in res.tables.items():
            cols = schema.get("columns", [])
            lines.append(f"\n### Table: `{t_name}` ({schema.get('row_count', 0)} rows)")
            lines.append("| Column | Type | PK | Nullable | Default |")
            lines.append("|---|---|---|---|---|")
            for c in cols:
                lines.append(f"| `{c['name']}` | `{c['data_type']}` | {'✅' if c['primary_key'] else '❌'} | {'❌' if c['not_null'] else '✅'} | `{c.get('default_value') or ''}` |")

        if res.sqlalchemy_models:
            lines.extend([
                "\n## 💻 Reconstructed Python SQLAlchemy Models",
                "```python",
                res.sqlalchemy_models,
                "```",
            ])

        return "\n".join(lines)

    def _build_device_markdown(self, res: Any) -> str:
        lines = [
            f"# 🔌 REA Teardown Report: {res.target}",
            f"**Scan Type:** `{res.device_type}`\n",
            f"**Summary:** {res.reconstructed_profile}\n",
        ]

        if res.open_ports:
            lines.extend([
                "## 🌐 Discovered Open Ports & Services",
                "| Port | Service | Status | Banner |",
                "|---|---|---|---|",
                *[f"| `{p['port']}` | `{p['service']}` | `{p['status']}` | `{p.get('banner') or ''}` |" for p in res.open_ports],
            ])

        if res.devices_found:
            lines.append("\n## 🖥️ Devices Found")
            for dev in res.devices_found[:25]:
                lines.append(f"- `{json.dumps(dev)}`")

        return "\n".join(lines)
