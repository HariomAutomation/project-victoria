"""
Victoria — Sanity / Smoke / Regression test suite.

Run from anywhere:
    python3 -m pytest tests/test_victoria.py -v

(If `victoria` isn't importable, run with PYTHONPATH set to the repo root:
    PYTHONPATH=. python3 -m pytest tests/test_victoria.py -v)

Sections:
  SANITY     - repo structure, config, packaging, no leaked secrets
  SMOKE      - does it actually start and serve?
  REGRESSION - every bug we fixed must stay fixed
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


def _find_repo() -> Path:
    """Locate the repo root: env override -> tests/.. -> cwd."""
    env = os.environ.get("VICTORIA_REPO")
    if env:
        return Path(env).resolve()
    for base in (Path(__file__).resolve().parent.parent, Path.cwd()):
        if (base / "victoria" / "main.py").exists():
            return base
    return Path.cwd()


REPO = _find_repo()


# ===========================================================================
# Session fixtures (built once — the HUD import spawns the MCP/REA server)
# ===========================================================================

@pytest.fixture(scope="session")
def hud():
    from fastapi.testclient import TestClient
    import victoria.hud.server as srv
    return {
        "app": srv.app,
        "client": TestClient(srv.app),
        "registry": srv.tool_registry,
    }


@pytest.fixture(scope="session")
def cfg():
    from victoria.config import get_config
    return get_config()


@pytest.fixture()
def restore_state():
    """Back up config/victoria.yaml and .env, restore both after a mutating test."""
    cfg_path = REPO / "config" / "victoria.yaml"
    env_path = REPO / ".env"
    cfg_backup = cfg_path.read_text(encoding="utf-8")
    env_backup = env_path.read_text(encoding="utf-8") if env_path.exists() else None
    yield
    cfg_path.write_text(cfg_backup, encoding="utf-8")
    if env_backup is None:
        env_path.unlink(missing_ok=True)
    else:
        env_path.write_text(env_backup, encoding="utf-8")


# ===========================================================================
# SANITY
# ===========================================================================

SANITY_FILES = [
    "README.md", "LICENSE", "pyproject.toml", "requirements.txt",
    ".env.example", "config/victoria.yaml",
    "victoria/main.py", "victoria/config.py",
    "victoria/brain/router.py", "victoria/brain/tools.py",
    "victoria/brain/model_discovery.py",
    "victoria/brain/mcp_client.py", "victoria/brain/mcp_bridge.py",
    "victoria/hud/server.py", "victoria/hud/ide_api.py",
    "victoria/hud/static/index.html", "victoria/hud/static/ide.html",
    "victoria/hud/static/js/app.js", "victoria/hud/static/js/ide.js",
    "victoria/hud/static/css/hud.css", "victoria/hud/static/css/ide.css",
]


@pytest.mark.parametrize("rel", SANITY_FILES)
def test_repo_structure(rel):
    assert (REPO / rel).exists(), f"missing required file: {rel}"


def test_compile_all():
    r = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "victoria"],
        cwd=REPO, capture_output=True, text=True,
    )
    assert r.returncode == 0, f"compileall failed:\n{r.stdout}\n{r.stderr}"


def test_config_loads(cfg):
    assert cfg.assistant_name
    models = cfg.get("brain.models", {})
    assert "gemini" in models
    assert cfg.get_active_model_name() in models


def test_pyproject_is_buildable():
    txt = (REPO / "pyproject.toml").read_text()
    assert 'build-backend = "setuptools.build_meta"' in txt
    assert "setuptools.backends._legacy" not in txt  # the old broken value
    assert 'license = "MIT"' in txt


def test_license_file_is_mit():
    txt = (REPO / "LICENSE").read_text()
    assert "MIT License" in txt


def test_requirements_no_dead_deps():
    txt = (REPO / "requirements.txt").read_text()
    assert "dbus-python" not in txt
    assert "scipy" not in txt
    assert "faster-whisper" in txt


def test_env_is_gitignored_and_no_secrets_tracked():
    """A local .env is expected (the owner keeps keys there) — it must simply be
    gitignored, and no real keys may appear in any source file."""
    gitignore = (REPO / ".gitignore").read_text()
    assert re.search(r"^\.env$", gitignore, re.M), ".env must be gitignored"

    patterns = ["sk-or-v1-", "sk-ant-", "AIzaSy", "gsk_", "AQ.Ab8"]
    hits = []
    for p in REPO.rglob("*"):
        if not p.is_file() or ".git" in p.parts:
            continue
        if p.name == ".env" or "tests" in p.parts or p.suffix.lower() in {".png", ".jpg", ".ico", ".db", ".pyc"}:
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat in patterns:
            for line in txt.splitlines():
                if pat in line and "placeholder" not in line.lower() and "..." not in line:
                    # allow the detector regexes inside web_inspector.py
                    if "re.findall" in line or "secret_patterns" in line or "r'" in line or 'r"' in line:
                        continue
                    hits.append(f"{p.relative_to(REPO)}: {pat}")
    assert not hits, f"possible leaked secrets: {hits}"


def test_js_syntax():
    if not _which("node"):
        pytest.skip("node not available")
    for js in ["victoria/hud/static/js/app.js", "victoria/hud/static/js/ide.js"]:
        r = subprocess.run(["node", "--check", js], cwd=REPO, capture_output=True, text=True)
        assert r.returncode == 0, f"{js}: {r.stderr}"


def _which(cmd):
    from shutil import which
    return which(cmd)


# ===========================================================================
# SMOKE
# ===========================================================================

def test_tool_registry_builds(hud):
    names = hud["registry"].list_tools()
    assert len(names) >= 46, f"expected >=46 built-in tools, got {len(names)}"
    # core tools must exist
    for t in ["open_application", "set_volume", "take_screenshot",
              "get_system_info", "run_terminal_command", "toggle_mute"]:
        assert t in names, f"missing tool: {t}"


def test_brain_router_instantiates(hud):
    from victoria.brain.router import BrainRouter
    r = BrainRouter(tool_registry=hud["registry"])
    assert r.get_active_model_info()


def test_cli_status_runs():
    r = subprocess.run(
        [sys.executable, "-m", "victoria", "--status"],
        cwd=REPO, capture_output=True, text=True, timeout=240,
        env={**os.environ, "PYTHONPATH": str(REPO)},
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert "tools registered" in r.stdout


def test_hud_status_endpoint(hud):
    d = hud["client"].get("/api/status").json()
    assert d["status"] == "online"
    assert d["tools_count"] >= 46
    assert "active_model" in d


def test_hud_serves_index_and_ide(hud):
    assert hud["client"].get("/").status_code == 200
    assert hud["client"].get("/ide").status_code == 200


# ===========================================================================
# REGRESSION — each fixed bug must stay fixed
# ===========================================================================

def test_regression_offline_volume_uses_level_param(hud):
    """Bug: offline handler called set_volume(volume_percent=...) but param is `level`."""
    router = _router(hud)
    # must not raise / must return a real reply (not None)
    out = router._handle_offline_command("volume badhao")
    assert out and "volume" in out.lower()


def test_regression_offline_app_uses_open_application(hud):
    """Bug: offline handler called `launch_application` which isn't registered."""
    router = _router(hud)
    out = router._handle_offline_command("chrome kholo")
    assert out and "chrome" in out.lower()
    # and the registry must NOT contain a bogus launch_application name
    assert "launch_application" not in hud["registry"].list_tools()


def test_regression_mute_is_reachable_and_registered(hud):
    """Bug: 'mute karo' never reached the mute branch; toggle_mute wasn't registered."""
    router = _router(hud)
    out = router._handle_offline_command("mute karo")
    assert out is not None, "bare 'mute' must reach the mute handler"
    assert "toggle_mute" in hud["registry"].list_tools()


def test_regression_default_gemini_model_is_not_shut_down(cfg):
    """Bug: default was gemini-2.0-flash, shut down in 2026."""
    model = cfg.get("brain.models.gemini.model", "")
    assert "2.0" not in model, f"default gemini model is shut down: {model}"
    assert model.startswith("gemini-")


def test_regression_discover_models_endpoint(hud):
    r = hud["client"].get("/api/brain/discover-models", params={"provider": "gemini"})
    assert r.status_code == 200
    d = r.json()
    assert "models" in d and isinstance(d["models"], list)
    # never empty — curated fallback guarantees it
    assert len(d["models"]) > 0


def test_regression_discover_models_unknown_provider(hud):
    d = hud["client"].get("/api/brain/discover-models", params={"provider": "nope"}).json()
    assert d["status"] == "fallback"
    assert d["models"] == []


def test_regression_discover_models_openrouter_live(hud):
    try:
        d = hud["client"].get(
            "/api/brain/discover-models",
            params={"provider": "openrouter", "free_only": "true"},
        ).json()
    except Exception as e:
        pytest.skip(f"network unavailable: {e}")
    if not d.get("models"):
        pytest.skip("no network / OpenRouter unreachable")
    assert d["count"] > 0
    assert all(m.get("free") or m.get("free_tier") for m in d["models"][:5])


def test_regression_use_model_endpoint(hud, restore_state):
    r = hud["client"].post("/api/brain/use-model",
                           json={"provider": "openrouter", "model_id": "openrouter/free"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["active_model"] == "openrouter"
    assert d["model"] == "openrouter/free"


def test_regression_use_model_rejects_unknown_provider(hud):
    r = hud["client"].post("/api/brain/use-model",
                           json={"provider": "notreal", "model_id": "x"})
    assert r.status_code == 400


# ---- IDE surface ----

def test_regression_ide_info(hud):
    d = hud["client"].get("/api/ide/info").json()
    assert "workspace" in d and "allow_run" in d


def test_regression_ide_tree(hud):
    d = hud["client"].get("/api/ide/tree").json()
    names = {e["name"] for e in d["entries"]}
    assert "victoria" in names


def test_regression_ide_file_read(hud):
    d = hud["client"].get("/api/ide/file", params={"path": "README.md"}).json()
    assert d["path"] == "README.md"
    assert len(d["content"]) > 0
    assert d["language"] == "markdown"


def test_regression_ide_file_write_roundtrip(hud):
    rel = "_pytest_tmp.txt"
    try:
        r = hud["client"].post("/api/ide/file", json={"path": rel, "content": "hello"})
        assert r.status_code == 200
        d = hud["client"].get("/api/ide/file", params={"path": rel}).json()
        assert d["content"] == "hello"
    finally:
        (REPO / rel).unlink(missing_ok=True)


def test_regression_ide_run(hud):
    d = hud["client"].post("/api/ide/run", json={"command": "echo smoke-ok"}).json()
    assert d["code"] == 0
    assert "smoke-ok" in d["stdout"]


def test_regression_ide_search(hud):
    d = hud["client"].get("/api/ide/search", params={"q": "victoria"}).json()
    assert d["count"] > 0


def test_regression_ide_path_traversal_blocked(hud):
    for bad in ["../../etc/passwd", "..%2f..%2fetc%2fpasswd", "/etc/passwd"]:
        r = hud["client"].get("/api/ide/file", params={"path": bad})
        assert r.status_code in (400, 404), f"{bad} was not blocked (got {r.status_code})"


def test_regression_ide_run_disabled(hud, monkeypatch):
    """When ide.allow_run=false, /run must refuse."""
    import victoria.hud.ide_api as ide_api
    real_get = ide_api.get_config

    class FakeCfg:
        def get(self, key, default=None):
            if key == "ide.allow_run":
                return False
            return real_get().get(key, default)

    monkeypatch.setattr(ide_api, "get_config", lambda: FakeCfg())
    r = hud["client"].post("/api/ide/run", json={"command": "echo x"})
    assert r.status_code == 403


# ---- MCP bridge ----

def test_regression_mcp_bridge_bad_command_is_resilient():
    from victoria.brain.tools import ToolRegistry
    from victoria.brain.mcp_bridge import load_mcp_servers
    reg = ToolRegistry()
    out = load_mcp_servers(reg, {"enabled": True, "servers": {"bad": {"command": "/nope/nope"}}})
    assert out == []
    assert reg.list_tools() == []


def test_regression_mcp_bridge_registers_and_calls(tmp_path):
    """End-to-end MCP bridge against a tiny mock stdio server."""
    mock = tmp_path / "mock_mcp.py"
    mock.write_text(MOCK_MCP_SERVER, encoding="utf-8")

    from victoria.brain.tools import ToolRegistry
    from victoria.brain.mcp_bridge import load_mcp_servers

    reg = ToolRegistry()
    out = load_mcp_servers(reg, {"enabled": True, "servers": {
        "mock": {"command": sys.executable, "args": [str(mock)], "tool_prefix": "rea", "timeout": 20}
    }})
    assert len(out) == 1
    assert "rea_ping" in reg.list_tools()

    res = reg.execute("rea_ping", {"msg": "hi"})
    assert "pong:hi" in res

    # raw schema must be carried through for providers
    defs = {d.name: d for d in reg.get_definitions()}
    assert defs["rea_ping"].raw_schema["type"] == "object"


# ---- provider raw_schema passthrough ----

def test_regression_raw_schema_openai_provider():
    from victoria.brain.providers.base_provider import ToolDefinition
    from victoria.brain.providers.openai_compatible_provider import OpenAICompatibleProvider
    p = OpenAICompatibleProvider({"model": "x", "base_url": "http://localhost:1/v1"})
    td = ToolDefinition(name="t", description="d", parameters=[],
                        raw_schema={"type": "object", "properties": {"a": {"type": "string"}}})
    conv = p._convert_tools([td])
    assert conv[0]["function"]["parameters"] == td.raw_schema


def test_regression_web_inspector_verify_ssl_param():
    from victoria.rea.web_inspector import WebInspector
    assert WebInspector(verify_ssl=True).verify_ssl is True
    assert WebInspector(verify_ssl=False).verify_ssl is False


def test_regression_audio_toggle_mute_exists():
    from victoria.tools import audio_control
    assert callable(getattr(audio_control, "toggle_mute", None))


# ---- hardening regressions ----

def test_regression_cors_is_localhost_only(hud):
    import re
    cors = [m for m in hud["app"].user_middleware if m.cls.__name__ == "CORSMiddleware"]
    assert cors, "CORSMiddleware missing"
    opts = cors[0].kwargs
    assert opts.get("allow_origins") != ["*"], "CORS must not be wildcard"
    rx = opts.get("allow_origin_regex", "")
    assert "localhost" in rx and re.search(r"127", rx)


def test_regression_hud_default_host_is_localhost():
    import inspect
    from victoria.hud.server import start_hud_server
    default = inspect.signature(start_hud_server).parameters["host"].default
    assert default == "127.0.0.1"


# ===========================================================================
# helpers
# ===========================================================================

def _router(hud):
    from victoria.brain.router import BrainRouter
    return BrainRouter(tool_registry=hud["registry"])


MOCK_MCP_SERVER = r'''
import sys, json

TOOLS = [{
    "name": "ping",
    "description": "Ping the mock server",
    "inputSchema": {"type": "object", "properties": {"msg": {"type": "string"}}, "required": []},
}]

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n"); sys.stdout.flush()

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    method = msg.get("method")
    rid = msg.get("id")
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "mock-rea", "version": "1.0"},
        }})
    elif method == "notifications/initialized":
        pass
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        args = (msg.get("params") or {}).get("arguments") or {}
        send({"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": "pong:" + str(args.get("msg", ""))}]
        }})
    elif rid is not None:
        send({"jsonrpc": "2.0", "id": rid, "result": {}})
'''
