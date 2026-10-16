"""
Victoria - IDE Surface API
A small, sandboxed file/workspace API that turns Victoria's HUD into a code
editor surface (Monaco + file tree + terminal + AI chat).

Everything is confined to a single workspace root (config: `ide.workspace`,
defaults to the project root). Path traversal outside the workspace is rejected.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from victoria.config import PROJECT_ROOT, get_config

router = APIRouter(prefix="/api/ide", tags=["ide"])

# Directories that are never worth showing / walking in a code tree.
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache",
             ".pytest_cache", ".ruff_cache", "dist", "build", ".next", ".cache"}

LANG_BY_EXT = {
    ".py": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".jsx": "javascript", ".json": "json",
    ".md": "markdown", ".html": "html", ".htm": "html", ".css": "css", ".scss": "scss",
    ".yaml": "yaml", ".yml": "yaml", ".sh": "shell", ".bash": "shell", ".txt": "plaintext",
    ".toml": "ini", ".ini": "ini", ".cfg": "ini", ".rs": "rust", ".go": "go",
    ".java": "java", ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp",
    ".sql": "sql", ".xml": "xml", ".env": "ini",
}

MAX_FILE_BYTES = 2_000_000


def _workspace_root() -> Path:
    cfg = get_config()
    ws = cfg.get("ide.workspace") or "."
    p = Path(str(ws)).expanduser()
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve()
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p.resolve()


def _safe(rel: Optional[str]) -> Path:
    """Resolve `rel` inside the workspace; reject anything that escapes it."""
    root = _workspace_root()
    rel = (rel or "").strip().lstrip("/\\")
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(status_code=400, detail="Path is outside the workspace")
    return target


def _rel(path: Path) -> str:
    try:
        return path.relative_to(_workspace_root()).as_posix()
    except Exception:
        return path.name


@router.get("/info")
def ide_info():
    root = _workspace_root()
    return {
        "workspace": str(root),
        "name": root.name,
        "allow_run": bool(get_config().get("ide.allow_run", True)),
        "run_timeout": int(get_config().get("ide.run_timeout", 20)),
    }


@router.get("/tree")
def ide_tree(path: str = ""):
    d = _safe(path)
    if not d.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    if not d.is_dir():
        raise HTTPException(status_code=400, detail="Not a directory")

    entries = []
    try:
        children = list(d.iterdir())
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    for child in sorted(children, key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name in SKIP_DIRS:
            continue
        try:
            is_dir = child.is_dir()
            size = 0 if is_dir else child.stat().st_size
        except OSError:
            continue
        entries.append({
            "name": child.name,
            "path": _rel(child),
            "type": "dir" if is_dir else "file",
            "size": size,
        })
    return {"path": _rel(d) if d != _workspace_root() else "", "entries": entries}


@router.get("/file")
def ide_read_file(path: str):
    f = _safe(path)
    if not f.exists() or not f.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if f.stat().st_size > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="File too large to open (>2MB)")
    try:
        content = f.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot read file: {e}")
    return {
        "path": _rel(f),
        "content": content,
        "size": f.stat().st_size,
        "language": LANG_BY_EXT.get(f.suffix.lower(), "plaintext"),
    }


class SaveFileRequest(BaseModel):
    path: str
    content: str


@router.post("/file")
def ide_save_file(req: SaveFileRequest):
    f = _safe(req.path)
    if f.exists() and f.is_dir():
        raise HTTPException(status_code=400, detail="Path is a directory")
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(req.content, encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot write file: {e}")
    return {"status": "ok", "path": _rel(f), "size": f.stat().st_size}


class RunRequest(BaseModel):
    command: str
    cwd: Optional[str] = None


@router.post("/run")
def ide_run(req: RunRequest):
    cfg = get_config()
    if not cfg.get("ide.allow_run", True):
        raise HTTPException(status_code=403, detail="Command execution is disabled (ide.allow_run=false)")
    command = (req.command or "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="Empty command")

    cwd = _safe(req.cwd or "")
    if not cwd.is_dir():
        cwd = _workspace_root()
    timeout = int(cfg.get("ide.run_timeout", 20))

    try:
        proc = subprocess.run(
            command, shell=True, cwd=str(cwd),
            capture_output=True, text=True, timeout=timeout,
        )
        return {
            "code": proc.returncode,
            "stdout": proc.stdout[-20000:],
            "stderr": proc.stderr[-20000:],
            "cwd": str(cwd),
        }
    except subprocess.TimeoutExpired:
        return {"code": 124, "stdout": "", "stderr": f"⏱ Timed out after {timeout}s", "cwd": str(cwd)}
    except Exception as e:
        return {"code": 1, "stdout": "", "stderr": f"Error: {e}", "cwd": str(cwd)}


@router.get("/search")
def ide_search(q: str, path: str = "", max_results: int = 60):
    """Simple recursive text search inside the workspace."""
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Query too short")
    root = _safe(path)
    results = []
    ql = q.lower()

    for p in root.rglob("*"):
        if len(results) >= max_results:
            break
        if not p.is_file() or any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
                                ".zip", ".gz", ".so", ".onnx", ".bin", ".pyc"}:
            continue
        try:
            if p.stat().st_size > 500_000:
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if ql in line.lower():
                    results.append({"path": _rel(p), "line": i, "text": line.strip()[:200]})
                    if len(results) >= max_results:
                        break
        except Exception:
            continue
    return {"query": q, "count": len(results), "results": results}
