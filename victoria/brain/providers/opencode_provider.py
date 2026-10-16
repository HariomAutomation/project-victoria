"""
Victoria - OpenCode AI Provider
Integrates the local OpenCode CLI (opencode v2.x) to run free models without needing external paid keys:
  - DeepSeek V4.1 Flash Free (deepseek-v4.1-flash-free)
  - Xiaomi MiMo V2.6 Flash Free (mimo-v2.6-flash-free)
  - NVIDIA Nemotron 3.5 Lightning Free (nemotron-3.5-lightning-free)
  - Nemotron 3 Ultra Free (nemotron-3-ultra-free)
  - GLM 5.3 Flash Free (glm-5.3-flash-free)
  - LongCat 2.5 Preview Free (longcat-2.5-preview-free)
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional
from rich.console import Console

from victoria.brain.providers.base_provider import (
    BaseProvider, BrainResponse, Message, ToolDefinition, ToolCall
)

console = Console()


class OpenCodeProvider(BaseProvider):
    """
    AI Brain Provider connecting directly to OpenCode's local engine.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        raw_model = config.get("model", "deepseek-v4.1-flash-free")
        if "/" in raw_model:
            self.model_name = raw_model.split("/")[-1]
        else:
            self.model_name = raw_model

        self.cli_path = shutil.which("opencode") or "/usr/local/bin/opencode"

    def is_available(self) -> bool:
        """Check if OpenCode CLI is installed and accessible on this system."""
        return bool(shutil.which("opencode") or Path("/usr/local/bin/opencode").exists())

    def chat(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        system_prompt: Optional[str] = None,
    ) -> BrainResponse:
        """
        Send a conversation turn to OpenCode and stream/parse back the response.
        """
        prompt_parts = []
        if system_prompt:
            prompt_parts.append(f"System: {system_prompt}")

        for msg in messages:
            if msg.role == "system":
                prompt_parts.append(f"System: {msg.content}")
            elif msg.role == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                if msg.content:
                    prompt_parts.append(f"Victoria: {msg.content}")
            elif msg.role == "tool":
                prompt_parts.append(f"Tool Result ({msg.name or 'system'}): {msg.content}")

        full_prompt = "\n\n".join(prompt_parts)
        model_name = self.model_name
        if not model_name.startswith("opencode/"):
            model_slug = f"opencode/{model_name}"
        else:
            model_slug = model_name

        cmd = [self.cli_path, "run", "--format", "json", "--model", model_slug, full_prompt]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if proc.returncode != 0:
                err_text = proc.stderr.strip() or proc.stdout.strip()
                raise RuntimeError(f"OpenCode ({model_slug}) error [{proc.returncode}]: {err_text}")

            text_chunks = []
            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if event.get("type") == "text":
                        part = event.get("part", {})
                        chunk = part.get("text", "")
                        if chunk:
                            text_chunks.append(chunk)
                except Exception:
                    pass

            final_text = "".join(text_chunks).strip()
            if not final_text:
                final_text = proc.stdout.strip()

            return BrainResponse(
                text=final_text,
                model_used=self.model_name,
                raw_response=proc.stdout,
            )

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"OpenCode model '{self.model_name}' timed out after 60 seconds.")
        except Exception as e:
            console.print(f"[red]❌ OpenCode provider error: {e}[/red]")
            raise
