"""
Victoria - LeanToken Code Intelligence & Token Optimizer Tool
Integrates https://github.com/morluto/leantoken into Project Victoria.

Minimizes AI LLM token usage by:
- Serving bounded, ranked code context within strict token budgets
- Generating structural code outlines without reading full files
- Reading exact line ranges instead of entire massive source files
- Indexing repositories into local SQLite database for instant retrieval
- Tracking token compression and context savings
"""

import json
import subprocess
from pathlib import Path
from typing import Optional
from rich.console import Console

from victoria.config import PROJECT_ROOT

console = Console()


def _run_leantoken(args: list[str], root_dir: Optional[str] = None, timeout: int = 20) -> tuple[int, str]:
    """Execute leantoken via npx with specified arguments."""
    root = str(Path(root_dir).resolve()) if root_dir else str(PROJECT_ROOT)
    cmd = ["npx", "-y", "leantoken", *args, "--root", root, "--json"]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout.strip() or res.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "LeanToken command timed out."
    except Exception as e:
        return 1, f"Failed to execute LeanToken: {e}"


def index_repository(root_dir: Optional[str] = None) -> str:
    """
    Index the codebase into LeanToken's local SQLite cache for instant, token-efficient retrieval.

    Args:
        root_dir: Repository root to index (default: current project root)

    Returns:
        Status message with files indexed count.
    """
    code, output = _run_leantoken(["index"], root_dir)
    if code == 0:
        try:
            data = json.loads(output)
            return (
                f"✅ LeanToken indexed {data.get('files_indexed', 0)} files "
                f"(scope: {data.get('index_scope', 'full')}, gen: {data.get('repository_generation', 1)})."
            )
        except Exception:
            return f"✅ LeanToken index complete:\n{output[:300]}"
    return f"❌ LeanToken indexing failed: {output}"


def get_lean_context(task: str, budget: int = 2000, root_dir: Optional[str] = None) -> str:
    """
    Retrieve ranked task context strictly bounded by a token budget to save AI tokens.

    Args:
        task: Description of what you are working on or trying to understand
        budget: Maximum token budget (default: 2000 tokens)
        root_dir: Repository root path

    Returns:
        Compact code snippets relevant to the task without token waste.
    """
    args = ["context", "--task", task, "--budget", str(budget)]
    code, output = _run_leantoken(args, root_dir)

    if code == 0:
        try:
            data = json.loads(output)
            fragments = data.get("fragments", [])
            meta = data.get("meta", {})

            result = [
                f"🧠 LeanToken Context ({len(fragments)} fragments, {meta.get('source_tokens', 0)} tokens used out of {budget} budget):\n"
            ]
            for f in fragments:
                result.append(f"📄 `{f['path']}` (Lines {f['start_line']}-{f['end_line']}):")
                result.append("```python")
                result.append(f["content"].strip())
                result.append("```\n")

            return "\n".join(result)
        except Exception:
            return output[:1500]
    return f"LeanToken context error: {output}"


def lean_search(query: str, root_dir: Optional[str] = None) -> str:
    """
    Search symbols, functions, classes, and terms across the codebase using LeanToken.

    Args:
        query: Term, symbol name, or regex pattern to search

    Returns:
        Ranked matches with paths and line numbers.
    """
    args = ["search", query]
    code, output = _run_leantoken(args, root_dir)
    if code == 0:
        try:
            data = json.loads(output)
            matches = data.get("matches", [])
            lines = [f"🔍 LeanToken Search for '{query}' ({len(matches)} matches):"]
            for m in matches[:15]:
                lines.append(f"• `{m.get('path')}` (L{m.get('line_number', 0)}): {m.get('line_content', '').strip()}")
            return "\n".join(lines)
        except Exception:
            return output[:1500]
    return f"Search error: {output}"


def lean_outline(file_path: str, root_dir: Optional[str] = None) -> str:
    """
    Get the structural outline (classes, functions, methods, imports) of a file without spending tokens on the full file body.

    Args:
        file_path: Path to the source file

    Returns:
        Structural outline of the file.
    """
    args = ["outline", file_path]
    code, output = _run_leantoken(args, root_dir)
    if code == 0:
        try:
            data = json.loads(output)
            return f"📋 Structural Outline of `{file_path}`:\n" + json.dumps(data, indent=2)[:1500]
        except Exception:
            return output[:1500]
    return f"Outline error: {output}"


def lean_read_range(file_path: str, start_line: int, end_line: int, root_dir: Optional[str] = None) -> str:
    """
    Read a bounded line range from a file to save tokens.

    Args:
        file_path: Path to the file
        start_line: 1-indexed starting line
        end_line: 1-indexed ending line

    Returns:
        The exact requested code lines.
    """
    args = ["read", file_path, f"{start_line}:{end_line}"]
    code, output = _run_leantoken(args, root_dir)
    if code == 0:
        try:
            data = json.loads(output)
            return f"📄 `{file_path}` (L{start_line}-L{end_line}):\n" + data.get("content", output)
        except Exception:
            return output
    return f"Read range error: {output}"


def get_token_savings(root_dir: Optional[str] = None) -> str:
    """
    Get LeanToken source compression and full-response token accounting statistics.
    """
    code, output = _run_leantoken(["status"], root_dir)
    if code == 0:
        try:
            data = json.loads(output)
            return (
                f"📊 LeanToken Savings & Index Status:\n"
                f"• Indexed Source: {data.get('indexed_source_bytes', 0):,} bytes\n"
                f"• Total Files: {data.get('file_count', 0)}\n"
                f"• Symbols Cached: {data.get('symbol_count', 0)}\n"
                f"• Index State: {data.get('index_state', 'ready')}\n"
                f"• SQLite DB: {data.get('database_path')}"
            )
        except Exception:
            return output[:1000]
    return f"Savings report error: {output}"
