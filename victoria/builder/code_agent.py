"""
Victoria - Code Builder Agent (Phase 3)
Takes REA Teardown results and generates:
- Working Mock API Servers (FastAPI / Flask)
- Frontend Clones & Skeletons (HTML/CSS/JS with exact design tokens)
- Python SDK Clients
- Database Models & SQLite databases
"""

import json
import re
from pathlib import Path
from typing import Optional
from rich.console import Console

from victoria.config import PROJECT_ROOT

console = Console()


class CodeBuilderAgent:
    """
    Code generation engine that translates reverse-engineered specifications
    into executable, runnable codebases.
    """

    def __init__(self, builds_dir: Optional[str] = None):
        self.builds_dir = Path(builds_dir) if builds_dir else PROJECT_ROOT / "data" / "builds"
        self.builds_dir.mkdir(parents=True, exist_ok=True)

    def build_mock_server_from_teardown(self, teardown_json_path: str, port: int = 8000) -> str:
        """
        Generate and save a runnable FastAPI mock server mimicking the discovered endpoints.

        Args:
            teardown_json_path: Path to the teardown JSON report file
            port: Port for the mock server to run on

        Returns:
            Path to the generated mock server Python file.
        """
        with open(teardown_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        findings = data.get("findings", {})
        endpoints = findings.get("endpoints", [])
        project_slug = re.sub(r"[^a-zA-Z0-9_]", "_", data.get("target", "mock_server"))[:30]

        project_dir = self.builds_dir / f"mock_{project_slug}"
        project_dir.mkdir(parents=True, exist_ok=True)
        server_file = project_dir / "server.py"

        lines = [
            "# Auto-generated Mock Server by Project Victoria REA",
            f"# Target: {data.get('target')}",
            "from fastapi import FastAPI, Request",
            "import uvicorn\n",
            "app = FastAPI(title='REA Reconstructed Mock API')\n",
            "@app.get('/')",
            "def root():",
            "    return {'status': 'active', 'generator': 'Project Victoria REA Engine'}\n",
        ]

        seen_paths = set()
        allowed_methods = {"get", "post", "put", "delete", "patch", "head", "options"}
        for i, ep in enumerate(endpoints[:30]):
            url = ep.get("url", "")
            method = str(ep.get("method", "GET") or "GET").lower()
            if method not in allowed_methods:
                # An unknown/empty method would generate an invalid decorator
                method = "get"
            # Extract path
            path = re.sub(r"^https?://[^/]+", "", url)
            if not path or path == "/":
                continue
            # Sanitize path for FastAPI (strip query, escape quotes/newlines)
            path = re.sub(r"\?.*$", "", path)
            path = path.replace("'", "%27").replace('"', "%22").replace("\n", "").replace("\r", "")
            if not path.startswith("/"):
                path = "/" + path
            if path in seen_paths:
                continue
            seen_paths.add(path)

            lines.extend([
                f"@app.{method}('{path}')",
                f"async def mock_endpoint_{i}(request: Request):",
                f"    return {{'mock': True, 'path': '{path}', 'method': '{method.upper()}'}}\n",
            ])

        lines.extend([
            "if __name__ == '__main__':",
            f"    uvicorn.run(app, host='0.0.0.0', port={port})\n",
        ])

        server_file.write_text("\n".join(lines), encoding="utf-8")
        console.print(f"[green]✅ Mock server built: {server_file}[/green]")
        return str(server_file)

    def build_frontend_clone(self, teardown_json_path: str) -> str:
        """
        Generate an HTML/CSS/JS frontend clone based on extracted design tokens and forms.
        """
        with open(teardown_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        findings = data.get("findings", {})
        tokens = findings.get("design_tokens", {})
        colors = tokens.get("colors", ["#3b82f6", "#1e293b", "#f8fafc"])
        fonts = tokens.get("fonts", ["system-ui", "sans-serif"])

        primary_color = colors[0] if colors else "#3b82f6"
        bg_color = colors[1] if len(colors) > 1 else "#0f172a"
        text_font = fonts[0] if fonts else "Inter, system-ui, sans-serif"

        project_slug = re.sub(r"[^a-zA-Z0-9_]", "_", data.get("target", "clone"))[:30]
        project_dir = self.builds_dir / f"frontend_{project_slug}"
        project_dir.mkdir(parents=True, exist_ok=True)

        html_file = project_dir / "index.html"
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reconstructed Clone: {findings.get('title', 'Project Victoria')}</title>
    <style>
        :root {{
            --primary: {primary_color};
            --bg: {bg_color};
            --font: '{text_font}', system-ui, sans-serif;
        }}
        body {{
            margin: 0;
            padding: 0;
            background: var(--bg);
            color: #ffffff;
            font-family: var(--font);
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
        }}
        header {{
            width: 100%;
            padding: 1.5rem 2rem;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            text-align: center;
        }}
        .container {{
            max-width: 900px;
            width: 90%;
            margin: 3rem auto;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 2.5rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }}
        .badge {{
            display: inline-block;
            background: var(--primary);
            color: #fff;
            padding: 0.35rem 0.8rem;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 600;
        }}
        .api-list {{
            margin-top: 2rem;
            background: #00000040;
            padding: 1rem;
            border-radius: 8px;
            font-family: monospace;
            max-height: 250px;
            overflow-y: auto;
        }}
    </style>
</head>
<body>
    <header>
        <h2>⚡ Victoria REA Clone: {findings.get('title', 'Target')}</h2>
    </header>
    <main class="container">
        <span class="badge">Reconstructed Architecture</span>
        <h1>{findings.get('title', 'Target Application')}</h1>
        <p>{findings.get('description', 'Recovered via Victoria REA Deep Engine')}</p>
        
        <h3>Recovered API Surface ({len(findings.get('endpoints', []))} endpoints)</h3>
        <div class="api-list">
            {'<br>'.join([f"&bull; [{ep.get('method')}] {ep.get('url')}" for ep in findings.get('endpoints', [])[:10]])}
        </div>
    </main>
</body>
</html>
"""
        html_file.write_text(html_content, encoding="utf-8")
        console.print(f"[green]✅ Frontend clone built: {html_file}[/green]")
        return str(html_file)
