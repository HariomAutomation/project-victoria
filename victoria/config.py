"""
Victoria Configuration Loader
Loads and validates config from victoria.yaml with environment variable support.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Optional
from rich.console import Console

console = Console()

# Project root directory (where pyproject.toml lives)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "victoria.yaml"


class VictoriaConfig:
    """Central configuration manager for Victoria."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._raw: dict = {}
        self.load()

    def load(self):
        """Load configuration from YAML file and .env."""
        self.load_dotenv()
        if not self.config_path.exists():
            console.print(f"[red]❌ Config file not found: {self.config_path}[/red]")
            console.print("[yellow]📋 Copy config/victoria.yaml.example to config/victoria.yaml[/yellow]")
            raise FileNotFoundError(f"Config not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            self._raw = yaml.safe_load(f) or {}

        console.print(f"[green]✅ Config loaded from {self.config_path}[/green]")

    def reload(self):
        """Hot-reload configuration."""
        self.load()
        console.print("[cyan]🔄 Configuration reloaded[/cyan]")

    def get(self, dotted_key: str, default: Any = None) -> Any:
        """
        Get a config value using dot notation.
        Example: config.get("brain.active_model") -> "gemini"
        """
        keys = dotted_key.split(".")
        value = self._raw
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, dotted_key: str, value: Any, persist: bool = True):
        """
        Set a configuration value using dot notation and optionally persist to yaml.
        Example: config.set("voice.wake_word.sensitivity", 0.6)
        """
        keys = dotted_key.split(".")
        current = self._raw
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

        if persist:
            try:
                import yaml
                with open(self.config_path, "w", encoding="utf-8") as f:
                    yaml.dump(self._raw, f, default_flow_style=False, sort_keys=False)
                console.print(f"[green]💾 Persisted setting '{dotted_key}' = {value} to {self.config_path.name}[/green]")
            except Exception as e:
                console.print(f"[yellow]⚠️ Could not persist to {self.config_path}: {e}[/yellow]")

    def load_dotenv(self):
        """Load environment variables from PROJECT_ROOT / .env if present."""
        env_file = PROJECT_ROOT / ".env"
        if not env_file.exists():
            return
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("export "):
                        line = line[7:].strip()
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        os.environ[k] = v
        except Exception as e:
            console.print(f"[yellow]⚠️ Failed to load .env file: {e}[/yellow]")

    def save_env_variable(self, key: str, value: str):
        """Save an environment variable to .env file and current runtime os.environ."""
        env_file = PROJECT_ROOT / ".env"
        lines = []
        found = False
        if env_file.exists():
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except Exception:
                lines = []

        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"{key}=") or stripped.startswith(f"export {key}="):
                new_lines.append(f'{key}="{value}"\n')
                found = True
            else:
                new_lines.append(line)

        if not found:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f'{key}="{value}"\n')

        try:
            with open(env_file, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            console.print(f"[green]💾 Persisted {key} to {env_file.name}[/green]")
        except Exception as e:
            console.print(f"[red]❌ Error saving to .env: {e}[/red]")

        os.environ[key] = value

    def set_api_key(self, provider_or_var: str, api_key: str):
        """
        Store and persist an API key for a provider or specific environment variable.
        """
        provider_map = {
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "openai": "OPENAI_API_KEY",
            "groq": "GROQ_API_KEY",
            "sarvam": "SARVAM_API_KEY",
        }
        var_name = provider_map.get(provider_or_var.lower(), provider_or_var)
        clean_key = api_key.strip().strip("'\"")
        self.save_env_variable(var_name, clean_key)

    def get_api_key(self, env_var_name: str, quiet: bool = True) -> Optional[str]:
        """Get API key from environment variable, reloading .env if needed."""
        self.load_dotenv()
        key = os.environ.get(env_var_name)
        if not key and not quiet:
            console.print(f"[yellow]⚠️  API key not found in env: {env_var_name}[/yellow]")
        return key

    def get_model_config(self, model_name: Optional[str] = None) -> dict:
        """Get configuration for a specific model or the active model."""
        if model_name is None:
            model_name = self.get_active_model_name()

        models = self.get("brain.models", {})
        if model_name not in models:
            console.print(f"[red]❌ Model '{model_name}' not found in config[/red]")
            console.print(f"[yellow]Available models: {list(models.keys())}[/yellow]")
            raise ValueError(f"Model not configured: {model_name}")

        model_cfg = models[model_name].copy()
        # Resolve API key from environment
        if "api_key_env" in model_cfg:
            model_cfg["api_key"] = self.get_api_key(model_cfg["api_key_env"])

        # Dynamic override for OpenRouter if custom model is selected
        if model_name == "openrouter" or ("openrouter" in model_cfg.get("base_url", "").lower()):
            custom_model = os.environ.get("OPENROUTER_CUSTOM_MODEL")
            if custom_model:
                model_cfg["model"] = custom_model
        elif model_name == "opencode":
            custom_model = os.environ.get("OPENCODE_CUSTOM_MODEL")
            if custom_model:
                model_cfg["model"] = custom_model

        return model_cfg

    def set_openrouter_model(self, model_id: str):
        """Set and persist active model ID for OpenRouter."""
        self.save_env_variable("OPENROUTER_CUSTOM_MODEL", model_id)
        if "brain" in self._raw and "models" in self._raw["brain"]:
            if "openrouter" in self._raw["brain"]["models"]:
                self._raw["brain"]["models"]["openrouter"]["model"] = model_id
        console.print(f"[green]🌐 OpenRouter model set to: {model_id}[/green]")

    def set_opencode_model(self, model_id: str):
        """Set and persist active model ID for OpenCode."""
        self.save_env_variable("OPENCODE_CUSTOM_MODEL", model_id)
        if "brain" in self._raw and "models" in self._raw["brain"]:
            if "opencode" in self._raw["brain"]["models"]:
                self._raw["brain"]["models"]["opencode"]["model"] = model_id
        console.print(f"[green]🚀 OpenCode model set to: {model_id}[/green]")

    def get_active_model_name(self) -> str:
        """Get the name of the currently active model."""
        self.load_dotenv()
        env_active = os.environ.get("VICTORIA_ACTIVE_MODEL")
        if env_active:
            return env_active
        return self.get("brain.active_model", "gemini")

    def set_active_model(self, model_name: str, persist: bool = True):
        """Switch the active AI model and optionally persist to .env and yaml."""
        models = self.get("brain.models", {})
        if model_name not in models:
            raise ValueError(f"Model '{model_name}' not configured. Available: {list(models.keys())}")

        if "brain" not in self._raw:
            self._raw["brain"] = {}
        self._raw["brain"]["active_model"] = model_name

        if persist:
            self.save_env_variable("VICTORIA_ACTIVE_MODEL", model_name)

        console.print(f"[green]🧠 Brain switched to: {model_name}[/green]")

    def get_models_status(self) -> dict:
        """Return status of all models, API keys, and active selection."""
        self.load_dotenv()
        def mask_key(k: Optional[str]) -> Optional[str]:
            if not k:
                return None
            k = k.strip()
            if len(k) <= 8:
                return "••••••••"
            return f"{k[:4]}••••{k[-4:]}"

        models_dict = self.get("brain.models", {})
        active = self.get_active_model_name()

        model_list = []
        for name, cfg in models_dict.items():
            env_var = cfg.get("api_key_env")
            raw_key = os.environ.get(env_var) if env_var else None
            # Ollama & OpenCode models don't require an API key
            is_no_key = cfg.get("provider") in ("ollama", "opencode")
            has_key = is_no_key or bool(raw_key)

            model_list.append({
                "id": name,
                "provider": cfg.get("provider"),
                "model_name": cfg.get("model"),
                "api_key_env": env_var,
                "has_key": has_key,
                "masked_key": mask_key(raw_key) if not is_no_key else "Free Local Engine",
                "base_url": cfg.get("base_url"),
                "is_active": name == active,
            })

        providers_status = {
            "gemini": {
                "name": "Google Gemini",
                "env_var": "GEMINI_API_KEY",
                "has_key": bool(os.environ.get("GEMINI_API_KEY")),
                "masked_key": mask_key(os.environ.get("GEMINI_API_KEY")),
                "recommended": True,
                "doc_url": "https://aistudio.google.com/app/apikey",
            },
            "opencode": {
                "name": "OpenCode (Free Local Engine)",
                "env_var": None,
                "has_key": True,
                "masked_key": "Active Local Engine",
                "recommended": True,
                "doc_url": "https://opencode.ai",
            },
            "openrouter": {
                "name": "OpenRouter (Cloud Router)",
                "env_var": "OPENROUTER_API_KEY",
                "has_key": bool(os.environ.get("OPENROUTER_API_KEY")),
                "masked_key": mask_key(os.environ.get("OPENROUTER_API_KEY")),
                "recommended": False,
                "doc_url": "https://openrouter.ai/keys",
            },
            "openai": {
                "name": "OpenAI",
                "env_var": "OPENAI_API_KEY",
                "has_key": bool(os.environ.get("OPENAI_API_KEY")),
                "masked_key": mask_key(os.environ.get("OPENAI_API_KEY")),
                "recommended": False,
                "doc_url": "https://platform.openai.com/api-keys",
            },
            "groq": {
                "name": "Groq Cloud",
                "env_var": "GROQ_API_KEY",
                "has_key": bool(os.environ.get("GROQ_API_KEY")),
                "masked_key": mask_key(os.environ.get("GROQ_API_KEY")),
                "recommended": False,
                "doc_url": "https://console.groq.com/keys",
            },
            "sarvam": {
                "name": "Sarvam AI",
                "env_var": "SARVAM_API_KEY",
                "has_key": bool(os.environ.get("SARVAM_API_KEY")),
                "masked_key": mask_key(os.environ.get("SARVAM_API_KEY")),
                "recommended": False,
                "doc_url": "https://dashboard.sarvam.ai",
            },
            "ollama": {
                "name": "Ollama (Offline Local)",
                "env_var": None,
                "has_key": True,
                "masked_key": None,
                "recommended": False,
                "doc_url": "https://ollama.com",
            }
        }

        return {
            "active_model": active,
            "models": model_list,
            "providers": providers_status,
        }


    # --- Convenience properties ---

    @property
    def assistant_name(self) -> str:
        return self.get("assistant.name", "Victoria")

    @property
    def wake_phrase(self) -> str:
        return self.get("assistant.wake_phrase", "hey victoria")

    @property
    def personality(self) -> str:
        return self.get("assistant.personality", "You are Victoria, a helpful AI assistant.")

    @property
    def stt_config(self) -> dict:
        return self.get("voice.stt", {})

    @property
    def tts_config(self) -> dict:
        return self.get("voice.tts", {})

    @property
    def vad_config(self) -> dict:
        return self.get("voice.vad", {})

    @property
    def speaker_verify_config(self) -> dict:
        return self.get("voice.speaker_verify", {})

    @property
    def audio_config(self) -> dict:
        return self.get("voice.audio", {})

    @property
    def memory_config(self) -> dict:
        return self.get("memory", {})

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"

    @property
    def voice_profiles_dir(self) -> Path:
        return PROJECT_ROOT / "config" / "voice_profiles"

    def ensure_directories(self):
        """Create all required data directories."""
        dirs = [
            self.data_dir / "memory",
            self.data_dir / "logs",
            self.data_dir / "teardowns",
            self.data_dir / "voice_samples",
            self.voice_profiles_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


# Global config instance (lazy loaded)
_config: Optional[VictoriaConfig] = None


def get_config(config_path: Optional[str] = None) -> VictoriaConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = VictoriaConfig(config_path)
        _config.ensure_directories()
    return _config
