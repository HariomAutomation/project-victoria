"""
Victoria - HUD Backend Server (FastAPI)
Powers the 3D Holographic AI Dashboard, REA Command Deck, and Real-time Telemetry.
"""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from rich.console import Console

console = Console()

from victoria.config import PROJECT_ROOT, get_config
from victoria.brain.tools import build_tool_registry
from victoria.brain.router import BrainRouter
from victoria.brain.memory import ConversationMemory
from victoria.rea.teardown import ReverseEngineerEngine
from victoria.tools import audio_control, screenshot
from victoria.brain import model_discovery

STATIC_DIR = Path(__file__).parent / "static"
TEARDOWNS_DIR = PROJECT_ROOT / "data" / "teardowns"
AUDIO_CACHE_DIR = PROJECT_ROOT / "data" / "audio_cache"
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Initialize AI Brain & Tools
tool_registry = build_tool_registry()
brain_router = BrainRouter(tool_registry=tool_registry)
memory = ConversationMemory()
rea_engine = ReverseEngineerEngine()

app = FastAPI(title="Project Victoria HUD API", version="2.0")

# The HUD can read/write files and run commands, so it must not be reachable
# cross-origin from arbitrary websites. Restrict CORS to localhost only.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    speak: bool = True


class REARequest(BaseModel):
    target: str
    target_type: str = "auto"


class ActionRequest(BaseModel):
    action: str
    value: Optional[str] = None


# Live voice pipeline state tracking (synced from voice events broadcaster)
_current_voice_state = "IDLE"

def _on_hud_voice_event(payload: dict):
    global _current_voice_state
    st = payload.get("state", "").upper()
    if st in ("LISTENING", "THINKING", "SPEAKING", "STANDBY"):
        _current_voice_state = "IDLE" if st == "STANDBY" else st

try:
    from victoria.voice.voice_events import VoiceEventListener
    _voice_event_listener = VoiceEventListener(on_event=_on_hud_voice_event)
    _voice_event_listener.start()
except Exception:
    pass


@app.get("/api/status")
def get_status():
    """Get Victoria's system health, model status, live hardware gauges, and voice state."""
    cfg = get_config()
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        battery = psutil.sensors_battery()
    except Exception:
        cpu, mem, disk, battery = 0, None, None, None

    return {
        "status": "online",
        "assistant_name": cfg.assistant_name,
        "active_model": cfg.get_active_model_name(),
        "available_models": list(cfg.get("brain.models", {}).keys()),
        "tools_count": len(tool_registry.list_tools()),
        "voice_state": _current_voice_state,
        "telemetry": {
            "cpu_percent": cpu,
            "ram_percent": mem.percent if mem else 0,
            "ram_used_gb": round(mem.used / (1024**3), 1) if mem else 0,
            "ram_total_gb": round(mem.total / (1024**3), 1) if mem else 0,
            "disk_percent": disk.percent if disk else 0,
            "battery_percent": battery.percent if battery else None,
            "battery_charging": battery.power_plugged if battery else None,
        }
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Send user message to Victoria's brain and optionally generate Hindi speech audio."""
    import asyncio
    user_text = req.message.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    session_id = "hud_web_session"

    # Brain thoughts & tool execution in thread so it doesn't block event loop
    response_text = await asyncio.to_thread(brain_router.think, user_text)

    # Save to memory
    if memory.enabled:
        memory.save_message(session_id=session_id, role="user", content=user_text)
        memory.save_message(
            session_id=session_id,
            role="assistant",
            content=response_text,
            model_used=brain_router._active_model,
        )

    audio_url = None
    if req.speak and response_text:
        try:
            import edge_tts
            cfg = get_config()
            voice = cfg.get("voice.tts.edge_tts.voice", "hi-IN-SwaraNeural")
            audio_hash = abs(hash(response_text)) % 10000000
            audio_file = AUDIO_CACHE_DIR / f"tts_{audio_hash}.mp3"

            communicate = edge_tts.Communicate(text=response_text, voice=voice)
            await communicate.save(str(audio_file))
            audio_url = f"/api/audio/{audio_file.name}"
        except Exception:
            pass

    return {
        "user_message": user_text,
        "response": response_text,
        "active_model": brain_router._active_model,
        "audio_url": audio_url,
    }


@app.get("/api/audio/{filename}")
def get_audio(filename: str):
    """Stream generated TTS speech audio file."""
    audio_path = AUDIO_CACHE_DIR / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(str(audio_path), media_type="audio/mpeg")


@app.post("/api/rea")
def run_rea(req: REARequest):
    """Trigger Reverse Engineer Anything teardown from HUD."""
    target = req.target.strip()
    if not target:
        raise HTTPException(status_code=400, detail="Target cannot be empty")

    report = rea_engine.teardown(target, target_type=req.target_type)
    return report


@app.get("/api/reports")
def list_reports():
    """List recent REA teardown reports."""
    TEARDOWNS_DIR.mkdir(parents=True, exist_ok=True)
    md_files = sorted(TEARDOWNS_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [
        {
            "filename": f.name,
            "title": f.stem.replace("_", " ").title(),
            "created_at": f.stat().st_mtime,
            "size": f.stat().st_size,
        }
        for f in md_files[:20]
    ]


@app.get("/api/reports/{filename}")
def get_report_content(filename: str):
    """Get markdown content of a teardown report."""
    filepath = TEARDOWNS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return {"filename": filename, "content": filepath.read_text(encoding="utf-8", errors="ignore")}


@app.post("/api/action")
def perform_action(req: ActionRequest):
    """Perform fast hardware/system action from HUD."""
    act = req.action.lower()
    if act == "screenshot":
        res = screenshot.take_screenshot()
        return {"status": "ok", "result": res}
    elif act == "volume_up":
        res = audio_control.set_volume("+10")
        return {"status": "ok", "result": res}
    elif act == "volume_down":
        res = audio_control.set_volume("-10")
        return {"status": "ok", "result": res}
    elif act == "volume_mute":
        res = audio_control.set_volume("mute")
        return {"status": "ok", "result": res}
    elif act == "switch_model" and req.value:
        brain_router.switch_model(req.value)
        get_config().set_active_model(req.value, persist=True)
        return {"status": "ok", "result": f"Switched to {req.value}"}
    return {"status": "unknown_action"}


class BrainKeyRequest(BaseModel):
    provider: str
    api_key: str
    model_name: Optional[str] = None
    base_url: Optional[str] = None
    set_active: bool = True


class BrainSelectRequest(BaseModel):
    model: str


@app.get("/api/brain/models")
def get_brain_models():
    """Get all available models, providers, active selection, and key presence."""
    cfg = get_config()
    return cfg.get_models_status()


@app.post("/api/brain/select")
def select_brain_model(req: BrainSelectRequest):
    """Switch the active AI model permanently."""
    cfg = get_config()
    try:
        brain_router.switch_model(req.model)
        cfg.set_active_model(req.model, persist=True)
        return {"status": "ok", "active_model": req.model, "message": f"Active AI Brain switched to {req.model}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/voice/status")
def get_voice_status():
    """Get owner voice enrollment and biometric security status."""
    import json
    from victoria.voice.voice_onboarding import is_owner_enrolled, get_profile_paths
    cfg = get_config()
    npy_path, meta_path = get_profile_paths()
    enrolled = is_owner_enrolled()
    meta = {}
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            pass

    return {
        "enrolled": enrolled,
        "security_mode": "Strict Owner Only" if enrolled else "Open / Onboarding Required",
        "threshold": cfg.get("voice.speaker_verify.threshold", 0.52),
        "model": "CAM++ Neural ONNX",
        "metadata": meta,
    }


@app.post("/api/voice/enroll")
async def trigger_voice_enroll():
    """Trigger interactive voice print enrollment recording sequence."""
    from victoria.voice.tts import TextToSpeech
    from victoria.voice.voice_events import broadcaster
    from victoria.voice.voice_onboarding import run_first_time_voice_enrollment
    import asyncio

    tts = TextToSpeech()
    loop = asyncio.get_event_loop()
    success = await loop.run_in_executor(None, run_first_time_voice_enrollment, tts, broadcaster, False)
    return {"status": "ok" if success else "failed", "enrolled": success}


class UseModelRequest(BaseModel):
    provider: str
    model_id: str


@app.post("/api/brain/use-model")
def use_discovered_model(req: UseModelRequest):
    """Activate a specific discovered model id for a provider and persist it."""
    cfg = get_config()
    provider = req.provider.lower().strip()
    model_id = req.model_id.strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="model_id cannot be empty")

    config_key_map = {
        "gemini": "gemini",
        "openrouter": "openrouter",
        "opencode": "opencode",
        "groq": "groq",
        "openai": "openai_gpt4o",
        "sarvam": "sarvam",
        "ollama": "local_fast",
    }
    config_key = config_key_map.get(provider)
    if not config_key:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    try:
        models = cfg.get("brain.models", {})
        if config_key in models:
            cfg._raw["brain"]["models"][config_key]["model"] = model_id
    except Exception:
        pass

    if provider == "openrouter":
        cfg.set_openrouter_model(model_id)
    elif provider == "opencode":
        cfg.set_opencode_model(model_id)

    try:
        import yaml
        with open(cfg.config_path, "w", encoding="utf-8") as f:
            yaml.dump(cfg._raw, f, default_flow_style=False, sort_keys=False)
    except Exception:
        pass

    brain_router.reload_provider(config_key)
    brain_router.switch_model(config_key)
    cfg.set_active_model(config_key, persist=True)

    return {
        "status": "ok",
        "provider": provider,
        "model": model_id,
        "active_model": config_key,
        "message": f"{provider} model set to {model_id}",
    }


@app.get("/api/brain/discover-models")
def discover_brain_models(
    provider: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    free_only: bool = False,
):
    """
    Live model discovery: query the provider's own /models endpoint using the
    supplied (or already-stored) API key and return the current list of models.
    Never returns an empty list (falls back to a curated set).
    """
    cfg = get_config()
    key = (api_key or "").strip().strip("'\"") or None

    if not key:
        env_map = {
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "groq": "GROQ_API_KEY",
            "openai": "OPENAI_API_KEY",
            "sarvam": "SARVAM_API_KEY",
        }
        env_var = env_map.get(provider.lower())
        if env_var:
            key = cfg.get_api_key(env_var) or None

    result = model_discovery.list_models(provider, api_key=key, base_url=base_url, free_only=free_only)

    if not result["models"]:
        fallback = model_discovery.curated_fallback(provider)
        result["models"] = fallback
        result["count"] = len(fallback)
        result["fallback"] = True
    else:
        result["fallback"] = False

    result["status"] = "ok" if result["ok"] else "fallback"
    return result


@app.get("/api/brain/openrouter/models")
def get_openrouter_free_models(api_key: Optional[str] = None):
    """Backwards-compatible alias: live list of OpenRouter free models."""
    import os
    result = discover_brain_models(provider="openrouter", api_key=api_key, free_only=True)
    models = result.get("models", [])
    return {
        "status": "ok",
        "total_free": len(models),
        "models": models,
        "current_selected": os.environ.get("OPENROUTER_CUSTOM_MODEL", "openrouter/free"),
    }


@app.post("/api/brain/api-key")
def connect_brain_api_key(req: BrainKeyRequest):
    """
    Validate, store, and persist an AI model API key, then activate the model.
    """
    provider = req.provider.lower().strip()
    cfg = get_config()

    if provider == "opencode":
        chosen_model = req.model_name or "deepseek-v4.1-flash-free"
        try:
            cfg._raw["brain"]["models"]["opencode"]["model"] = chosen_model
            import yaml
            with open(cfg.config_path, "w", encoding="utf-8") as f:
                yaml.dump(cfg._raw, f, default_flow_style=False, sort_keys=False)
        except Exception:
            pass
        brain_router.reload_provider("opencode")
        brain_router.switch_model("opencode")
        cfg.set_active_model("opencode", persist=True)
        return {
            "status": "ok",
            "provider": "opencode",
            "active_model": "opencode",
            "message": f"OpenCode model '{chosen_model}' activated successfully (Free Local Engine)!",
            "models_status": cfg.get_models_status(),
        }

    key = req.api_key.strip().strip("'\"")
    if not key:
        env_map = {
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "groq": "GROQ_API_KEY",
            "openai": "OPENAI_API_KEY",
            "sarvam": "SARVAM_API_KEY",
        }
        env_var = env_map.get(provider)
        if env_var:
            key = (cfg.get_api_key(env_var) or "").strip().strip("'\"")

    if not key:
        raise HTTPException(status_code=400, detail=f"API Key cannot be empty. कृपया {provider.upper()} API Key दर्ज करें या .env फ़ाइल में जोड़ें।")

    verified_model = None

    # 1. Verification Test
    try:
        if provider == "gemini":
            from google import genai
            client = genai.Client(api_key=key)

            # Map friendly selection or config keys to actual Google Gemini model IDs
            candidate_models = []
            if req.model_name and req.model_name.startswith("gemini-"):
                candidate_models.append(req.model_name)
            elif req.model_name == "gemini_pro":
                candidate_models.extend(["gemini-3.1-pro-preview", "gemini-3.8-flash", "gemini-flash-latest"])
            else:
                candidate_models.extend(["gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"])

            last_err = None
            for m in candidate_models:
                try:
                    res = client.models.generate_content(
                        model=m,
                        contents="Ping. Reply with OK.",
                    )
                    if res:
                        verified_model = m
                        break
                except Exception as ex:
                    last_err = ex
                    err_str = str(ex).lower()
                    if "api key not valid" in err_str or "api_key_invalid" in err_str:
                        raise Exception("Gemini API Key अमान्य (Invalid) है। कृपया Google AI Studio (https://aistudio.google.com/app/apikey) से सही Key कॉपी करें।")
                    continue

            if not verified_model:
                raise Exception(f"Gemini verification failed on candidate models: {last_err}")

        elif provider in ["openrouter", "opencode"]:
            import httpx
            # 1. Instant OpenRouter key authentication check (avoids inference queue timeouts)
            auth_url = "https://openrouter.ai/api/v1/auth/key"
            headers = {
                "Authorization": f"Bearer {key}",
                "HTTP-Referer": "https://victoria-assistant.local",
                "X-Title": "Victoria AI Assistant",
            }
            try:
                with httpx.Client(timeout=8.0) as http_client:
                    auth_resp = http_client.get(auth_url, headers=headers)
                    if auth_resp.status_code == 401:
                        raise Exception("OpenRouter API Key अमान्य (Unauthorized) है। कृपया https://openrouter.ai/keys से सही Key प्राप्त करें।")
                    elif auth_resp.status_code == 200:
                        verified_model = req.model_name if req.model_name and req.model_name not in ["openrouter", "openrouter/free"] else "nvidia/nemotron-3.5-lightning:free"
            except Exception as auth_err:
                if "अमान्य" in str(auth_err):
                    raise auth_err

            # Fallback to chat completions if auth/key endpoint was unreachable
            if not verified_model:
                base_url = req.base_url or "https://openrouter.ai/api/v1"
                candidate_models = []
                if req.model_name and req.model_name not in ["openrouter", "openrouter/free", "default"]:
                    candidate_models.append(req.model_name)
                candidate_models.extend([
                    "openrouter/free",
                    "nvidia/nemotron-3.5-lightning:free",
                    "cohere/north-mini-code:free",
                    "google/gemma-4-31b-it:free",
                    "liquid/lfm-2.5-2.6b:free",
                ])
                url = f"{base_url.rstrip('/')}/chat/completions"
                headers["Content-Type"] = "application/json"
                last_err = None
                with httpx.Client(timeout=14.0) as http_client:
                    for m in candidate_models:
                        payload = {
                            "model": m,
                            "messages": [{"role": "user", "content": "ping"}],
                            "max_tokens": 5,
                        }
                        try:
                            resp = http_client.post(url, json=payload, headers=headers)
                            if resp.status_code == 200:
                                verified_model = m
                                break
                            elif resp.status_code == 401:
                                raise Exception("OpenRouter API Key अमान्य (Unauthorized) है। कृपया https://openrouter.ai/keys से सही Key प्राप्त करें।")
                            else:
                                last_err = Exception(f"HTTP {resp.status_code}: {resp.text[:120]}")
                        except httpx.RequestError as re:
                            last_err = re

                if not verified_model:
                    raise last_err or Exception("OpenRouter verification failed")

        elif provider in ["openai", "groq", "sarvam"]:
            import httpx
            base_url = req.base_url
            if not base_url:
                if provider == "openai":
                    base_url = "https://api.openai.com/v1"
                elif provider == "groq":
                    base_url = "https://api.groq.com/openai/v1"
                elif provider == "sarvam":
                    base_url = "https://api.sarvam.ai/v1"

            test_model = req.model_name
            if not test_model:
                if provider == "openai":
                    test_model = "gpt-4o-mini"
                elif provider == "groq":
                    test_model = "llama-3.3-70b-versatile"
                elif provider == "sarvam":
                    test_model = "sarvam-2b-v0.5"

            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }
            url = f"{(base_url or '').rstrip('/')}/chat/completions"
            payload = {
                "model": test_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
            }
            with httpx.Client(timeout=14.0) as http_client:
                resp = http_client.post(url, json=payload, headers=headers)
                if resp.status_code == 401:
                    raise Exception(f"{provider.upper()} API Key अमान्य (Unauthorized) है। कृपया अपनी Key जाँचें।")
                elif resp.status_code != 200:
                    err_body = resp.text
                    raise Exception(f"HTTP {resp.status_code}: {err_body[:160]}")
            verified_model = test_model

    except Exception as e:
        error_msg = str(e)
        console.print(f"[red]❌ API Key verification failed: {error_msg}[/red]")
        raise HTTPException(
            status_code=400,
            detail=f"API Key verification failed: {error_msg}"
        )

    # 2. Persist API Key to .env and os.environ
    cfg.set_api_key(provider, key)

    # 3. Model selection and persistence
    chosen_model = None
    if provider == "gemini":
        chosen_model = "gemini_pro" if req.model_name == "gemini_pro" else "gemini"
        if verified_model:
            # Sync working verified model name into config
            if "brain" in cfg._raw and "models" in cfg._raw["brain"]:
                if chosen_model in cfg._raw["brain"]["models"]:
                    cfg._raw["brain"]["models"][chosen_model]["model"] = verified_model
            try:
                import yaml
                with open(cfg.config_path, "w", encoding="utf-8") as f:
                    yaml.dump(cfg._raw, f, default_flow_style=False, sort_keys=False)
            except Exception:
                pass
    elif provider in ["openrouter", "opencode"]:
        chosen_openrouter_model = verified_model or req.model_name or "openrouter/free"
        cfg.set_openrouter_model(chosen_openrouter_model)
        chosen_model = "openrouter"
    elif provider == "openai":
        chosen_model = "openai_gpt4o"
    elif provider == "groq":
        chosen_model = "groq"
    elif provider == "sarvam":
        chosen_model = "sarvam"
    else:
        chosen_model = req.model_name or "gemini"

    if req.set_active and chosen_model:
        try:
            brain_router.switch_model(chosen_model)
            cfg.set_active_model(chosen_model, persist=True)
        except Exception as e:
            console.print(f"[yellow]⚠️ Failed to switch model: {e}[/yellow]")
    else:
        brain_router.reload_provider()

    # Restart background voice daemon if active so it reloads the new credentials
    try:
        import subprocess
        subprocess.run(["systemctl", "--user", "restart", "victoria.service"], capture_output=True, timeout=4)
    except Exception:
        pass

    return {
        "status": "ok",
        "message": f"{provider.upper()} API key verified and saved successfully!",
        "active_model": brain_router._active_model,
        "verified_model": verified_model,
        "models_status": cfg.get_models_status(),
    }



@app.get("/api/memory")
def get_recent_memory():
    """Get conversation history."""
    return memory.get_recent_messages(session_id="hud_web_session", limit=20)


@app.get("/api/persona")
def get_owner_persona():
    """Get the current Owner Persona & Digital Twin profile and markdown dossier."""
    from victoria.brain.persona import get_persona_engine, PERSONA_MD
    engine = get_persona_engine()
    md_content = PERSONA_MD.read_text(encoding="utf-8") if PERSONA_MD.exists() else ""
    return {
        "profile": engine.profile,
        "markdown": md_content,
    }


class OwnerMemoryRequest(BaseModel):
    content: str
    category: str = "fact"
    title: str = ""
    tags: str = ""
    importance: int = 3


@app.get("/api/owner-memory")
def get_owner_memories(q: Optional[str] = None, category: Optional[str] = None, limit: int = 50):
    """Retrieve owner memories, with optional offline FTS search and category filtering."""
    from victoria.brain.owner_memory import get_owner_vault
    vault = get_owner_vault()
    if q:
        items = vault.search(query=q, category=category, limit=limit)
    else:
        items = vault.list_memories(category=category, limit=limit)
    stats = vault.get_stats()
    return {"memories": items, "stats": stats}


@app.post("/api/owner-memory")
def add_owner_memory(req: OwnerMemoryRequest):
    """Add a new memory to the local offline vault."""
    from victoria.brain.owner_memory import get_owner_vault
    vault = get_owner_vault()
    mem_id = vault.store(
        content=req.content,
        category=req.category,
        title=req.title,
        tags=req.tags,
        importance=req.importance,
    )
    return {"status": "ok", "id": mem_id}


@app.delete("/api/owner-memory/{memory_id}")
def delete_owner_memory_endpoint(memory_id: int):
    """Delete a memory by its ID."""
    from victoria.brain.owner_memory import get_owner_vault
    vault = get_owner_vault()
    success = vault.delete_memory(memory_id)
    return {"status": "ok" if success else "not_found"}


class AddRuleRequest(BaseModel):
    trigger: str
    rule_instruction: str
    rule_type: str = "correction"


@app.get("/api/experience")
def get_experience_stats():
    """Get Victoria's self-evolution stats, mastered task recipes, and learned rules."""
    from victoria.brain.experience import get_experience_engine
    engine = get_experience_engine()
    return engine.get_stats()


@app.post("/api/experience/rules")
def add_experience_rule(req: AddRuleRequest):
    """Explicitly teach Victoria a new behavior rule or correction."""
    from victoria.brain.experience import get_experience_engine
    engine = get_experience_engine()
    engine.add_rule(
        trigger=req.trigger,
        rule_instruction=req.rule_instruction,
        rule_type=req.rule_type,
        learned_from="Owner via HUD Deck",
    )
    return {"status": "ok", "message": "Rule learned and saved!"}


# IDE surface (Monaco editor + file tree + terminal + AI) — sandboxed to ide.workspace
from victoria.hud.ide_api import router as ide_router

app.include_router(ide_router)


@app.get("/ide", include_in_schema=False)
def ide_page():
    """Serve the Victoria IDE surface."""
    page = STATIC_DIR / "ide.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail="IDE page not found")
    return FileResponse(str(page))


# Mount static assets last, so /api/* and /ide take precedence
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def open_hud_window(url: str = "http://localhost:7860"):
    """Open Victoria 3D HUD in dedicated Chrome App Window or default browser."""
    import os
    import shutil
    import subprocess
    import webbrowser

    if "DISPLAY" not in os.environ and "WAYLAND_DISPLAY" not in os.environ:
        os.environ["DISPLAY"] = ":0"

    for browser in ["google-chrome", "google-chrome-stable", "chromium"]:
        if shutil.which(browser):
            try:
                subprocess.Popen(
                    [browser, f"--app={url}", "--class=VictoriaHUD", "--name=Victoria HUD"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return
            except Exception:
                pass

    try:
        webbrowser.open(url)
    except Exception:
        pass


def start_hud_server(host: str = "127.0.0.1", port: int = 7860, open_browser: bool = True):
    """Start the Victoria HUD web dashboard."""
    import socket
    import threading
    import time
    from rich.console import Console

    console = Console()
    url = f"http://localhost:{port}"

    # Check if server is already running on this port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        is_running = (s.connect_ex(("127.0.0.1", port)) == 0)

    if is_running:
        console.print(f"[bold green]🌐 Victoria HUD is already active and running at: {url}[/bold green]")
        if open_browser:
            console.print("[bold cyan]🚀 Opening Victoria 3D Holographic App Window...[/bold cyan]")
            open_hud_window(url)
        return

    if open_browser:
        def _delayed_open():
            time.sleep(1.2)
            open_hud_window(url)
        threading.Thread(target=_delayed_open, daemon=True).start()

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_hud_server()
