"""
Victoria - Dynamic Model Discovery
Queries each AI provider's own model-listing endpoint so Victoria can show the
*current* list of models available for a given API key, instead of a hard-coded
list that goes stale.

Supported providers:
  - gemini      -> Google Generative Language API  (/v1beta/models)
  - openrouter  -> OpenRouter                      (/api/v1/models)
  - groq        -> Groq Cloud (OpenAI-compatible)  (/openai/v1/models)
  - openai      -> OpenAI                          (/v1/models)
  - sarvam      -> Sarvam AI (OpenAI-compatible)   (/v1/models)
  - ollama      -> local Ollama                    (/api/tags)

Every function returns a list of normalized dicts:
    {
        "id": str,              # model id to pass to the provider
        "name": str,            # human-readable name
        "provider": str,
        "context_length": int,  # 0 when unknown
        "free": bool,           # definitively zero-cost (OpenRouter free, openrouter/free)
        "free_tier": bool,      # provider offers a free tier for this model
        "description": str,
    }
"""

from __future__ import annotations

from typing import Any, Optional

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

from rich.console import Console

console = Console()

DEFAULT_BASE_URLS = {
    "gemini": "https://generativelanguage.googleapis.com",
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
    "sarvam": "https://api.sarvam.ai/v1",
    "ollama": "http://localhost:11434",
}


def _entry(
    model_id: str,
    name: str,
    provider: str,
    context_length: int = 0,
    free: bool = False,
    free_tier: bool = False,
    description: str = "",
) -> dict[str, Any]:
    return {
        "id": model_id,
        "name": name or model_id,
        "provider": provider,
        "context_length": int(context_length or 0),
        "free": bool(free),
        "free_tier": bool(free_tier),
        "description": description or "",
    }


def _is_zero(value: Any) -> bool:
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Per-provider discovery
# ---------------------------------------------------------------------------

def _discover_gemini(api_key: Optional[str], base_url: Optional[str]) -> list[dict]:
    """Google Generative Language API: list models that support generateContent."""
    base = (base_url or DEFAULT_BASE_URLS["gemini"]).rstrip("/")
    url = f"{base}/v1beta/models"
    params = {"key": api_key} if api_key else {}

    with httpx.Client(timeout=15.0) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    out = []
    for m in data.get("models", []):
        methods = m.get("supportedGenerationMethods", []) or []
        if "generateContent" not in methods:
            continue  # skip embedding / pure-audio models
        raw_name = m.get("name", "")  # e.g. "models/gemini-3.8-flash"
        mid = raw_name.split("/", 1)[-1]
        # Google offers a free tier for its Flash / Flash-Lite models.
        is_free_tier = "flash" in mid.lower() or "gemini-2" in mid.lower()
        out.append(_entry(
            model_id=mid,
            name=m.get("displayName") or mid,
            provider="gemini",
            context_length=m.get("inputTokenLimit", 0),
            free_tier=is_free_tier,
            description=(m.get("description") or "")[:160],
        ))
    return out


def _discover_openrouter(api_key: Optional[str], base_url: Optional[str], free_only: bool = False) -> list[dict]:
    base = (base_url or DEFAULT_BASE_URLS["openrouter"]).rstrip("/")
    headers = {
        "HTTP-Referer": "https://victoria-assistant.local",
        "X-Title": "Victoria AI Assistant",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    with httpx.Client(timeout=20.0) as client:
        resp = client.get(f"{base}/models", headers=headers)
        resp.raise_for_status()
        data = resp.json().get("data", [])

    out = []
    for m in data:
        mid = m.get("id", "")
        pricing = m.get("pricing", {}) or {}
        is_free = (
            mid == "openrouter/free"
            or (":free" in mid)
            or (_is_zero(pricing.get("prompt")) and _is_zero(pricing.get("completion")))
        )
        if free_only and not is_free:
            continue
        out.append(_entry(
            model_id=mid,
            name=m.get("name") or mid,
            provider="openrouter",
            context_length=m.get("context_length", 0),
            free=is_free,
            description=(m.get("description") or "")[:160],
        ))

    # Free models first, then auto-router, then by name.
    out.sort(key=lambda x: (not x["free"], not x["id"].startswith("openrouter/free"), x["name"].lower()))
    return out


def _discover_openai_compatible(provider: str, api_key: Optional[str], base_url: Optional[str]) -> list[dict]:
    base = (base_url or DEFAULT_BASE_URLS.get(provider, "")).rstrip("/")
    if not base:
        return []
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    with httpx.Client(timeout=15.0) as client:
        resp = client.get(f"{base}/models", headers=headers)
        resp.raise_for_status()
        data = resp.json().get("data", [])

    out = []
    for m in data:
        mid = m.get("id", "")
        if not mid:
            continue
        # Groq exposes a free tier; OpenAI / Sarvam are paid.
        free_tier = provider == "groq"
        out.append(_entry(
            model_id=mid,
            name=mid,
            provider=provider,
            free_tier=free_tier,
        ))
    out.sort(key=lambda x: x["id"].lower())
    return out


def _discover_ollama(api_key: Optional[str], base_url: Optional[str]) -> list[dict]:
    base = (base_url or DEFAULT_BASE_URLS["ollama"]).rstrip("/")
    with httpx.Client(timeout=6.0) as client:
        resp = client.get(f"{base}/api/tags")
        resp.raise_for_status()
        data = resp.json().get("models", [])

    out = []
    for m in data:
        mid = m.get("name") or m.get("model", "")
        size_gb = round((m.get("size") or 0) / (1024 ** 3), 1)
        out.append(_entry(
            model_id=mid,
            name=f"{mid} ({size_gb} GB)" if size_gb else mid,
            provider="ollama",
            free=True,
            description="Runs locally — offline, private, no API cost",
        ))
    out.sort(key=lambda x: x["id"].lower())
    return out


def _discover_opencode() -> list[dict]:
    """Discover free models supported natively by local OpenCode CLI."""
    opencode_models = [
        ("deepseek-v4.1-flash-free", "DeepSeek V4.1 Flash Free (Ultra-Fast & Smart)", 200000),
        ("mimo-v2.6-flash-free", "Xiaomi MiMo-V2.6 Flash Free (Multimodal)", 200000),
        ("nemotron-3.5-lightning-free", "NVIDIA Nemotron 3.5 Lightning Free (1M Context)", 262144),
        ("glm-5.3-flash-free", "GLM-5.3 Flash Free", 200000),
        ("nemotron-3-ultra-free", "NVIDIA Nemotron 3 Ultra Free", 1000000),
        ("cat-jam-free", "Cat Jam Free", 1048576),
        ("space-bunny-free", "Space Bunny Free", 1048576),
        ("longcat-2.5-preview-free", "LongCat 2.5 Preview Free", 1000000),
        ("muse-spark-1.3-contributor-free", "Muse Spark 1.3 Free", 1048576),
    ]
    return [
        _entry(
            model_id=mid,
            name=name,
            provider="opencode",
            context_length=ctx,
            free=True,
            free_tier=True,
            description="100% Free local engine powered by OpenCode CLI",
        )
        for mid, name, ctx in opencode_models
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_models(
    provider: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    free_only: bool = False,
) -> dict[str, Any]:
    """
    Discover the models available for a provider.

    Returns a dict: {"provider", "ok", "count", "models", "error"}.
    Never raises — network/auth failures come back as ok=False with a message
    so the UI can fall back to a curated list.
    """
    provider = (provider or "").lower().strip()
    if httpx is None:
        return {"provider": provider, "ok": False, "count": 0, "models": [], "error": "httpx not installed"}

    try:
        if provider == "gemini":
            models = _discover_gemini(api_key, base_url)
        elif provider == "opencode":
            models = _discover_opencode()
        elif provider == "openrouter":
            models = _discover_openrouter(api_key, base_url, free_only=free_only)
        elif provider in ("groq", "openai", "sarvam"):
            models = _discover_openai_compatible(provider, api_key, base_url)
        elif provider == "ollama":
            models = _discover_ollama(api_key, base_url)
        else:
            return {"provider": provider, "ok": False, "count": 0, "models": [], "error": f"Unknown provider: {provider}"}

        if free_only:
            models = [m for m in models if m["free"] or m["free_tier"]]

        return {"provider": provider, "ok": True, "count": len(models), "models": models, "error": None}

    except Exception as e:  # noqa: BLE001 - surface any failure to the UI
        msg = str(e)
        console.print(f"[yellow]⚠️ Model discovery failed for {provider}: {msg}[/yellow]")
        return {"provider": provider, "ok": False, "count": 0, "models": [], "error": msg}


# Curated fallbacks (used only when the live call fails, e.g. offline).
CURATED_FREE_MODELS = [
    ("openrouter/free", "OpenRouter: Free Auto-Router (always free)", 200000),
    ("nvidia/nemotron-3.5-lightning:free", "NVIDIA: Nemotron 3.5 Lightning (Free, 1M ctx)", 1000000),
    ("cohere/north-mini-code:free", "Cohere: North Mini Code (Free)", 256000),
    ("liquid/lfm-2.5-2.6b:free", "LiquidAI: LFM2.5 2.6B (Free)", 65536),
    ("google/gemma-4-31b-it:free", "Google: Gemma 4 31B (Free)", 262144),
]


def curated_fallback(provider: str) -> list[dict]:
    """A small offline list so the UI is never empty."""
    provider = (provider or "").lower()
    if provider == "opencode":
        return _discover_opencode()
    if provider == "openrouter":
        return [_entry(mid, name, "openrouter", ctx, free=True) for mid, name, ctx in CURATED_FREE_MODELS]
    if provider == "gemini":
        return [
            _entry("gemini-3.8-flash", "Gemini 3.8 Flash (latest, fast)", "gemini", 1048576, free_tier=True),
            _entry("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite (cheapest)", "gemini", 1048576, free_tier=True),
            _entry("gemini-3.1-pro-preview", "Gemini 3.1 Pro (deep reasoning)", "gemini", 1048576),
            _entry("gemini-flash-latest", "Gemini Flash (latest alias)", "gemini", 1048576, free_tier=True),
        ]
    return []
