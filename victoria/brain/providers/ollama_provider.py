"""
Victoria - Ollama Provider (Local AI Models)
Connects to Ollama running locally for fully offline, free AI capabilities.
Supports all Ollama models: Gemma, Llama, Qwen, Mistral, etc.
"""

import json
from typing import Optional
from rich.console import Console

from victoria.brain.providers.base_provider import (
    BaseProvider, BrainResponse, Message, ToolCall, ToolDefinition
)

console = Console()


class OllamaProvider(BaseProvider):
    """
    Ollama Local AI Provider.
    Connects to a locally running Ollama instance for fully offline inference.
    No internet needed, no API costs, full privacy.
    """

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self.base_url = model_config.get("base_url", "http://localhost:11434")
        self._client = None

    def _get_client(self):
        """Lazy-load the Ollama client."""
        if self._client is None:
            try:
                import ollama
                self._client = ollama.Client(host=self.base_url)
                console.print(f"[green]✅ Ollama client initialized: {self.model_name} @ {self.base_url}[/green]")
            except ImportError:
                console.print("[red]❌ ollama package not installed. pip install ollama[/red]")
                raise
        return self._client

    def _convert_tools_to_ollama(self, tools: list[ToolDefinition]) -> list:
        """Convert tool definitions to Ollama/OpenAI function format."""
        ollama_tools = []
        for tool in tools:
            if getattr(tool, "raw_schema", None):
                parameters = tool.raw_schema
            else:
                properties = {}
                required = []

                for param in tool.parameters:
                    prop = {"type": param.type, "description": param.description}
                    if param.enum:
                        prop["enum"] = param.enum
                    properties[param.name] = prop
                    if param.required:
                        required.append(param.name)

                parameters = {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }

            ollama_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": parameters,
                },
            })
        return ollama_tools

    def _convert_messages_to_ollama(self, messages: list[Message], system_prompt: Optional[str] = None) -> list:
        """Convert messages to Ollama chat format."""
        ollama_messages = []

        if system_prompt:
            ollama_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            if msg.role == "system":
                ollama_messages.append({"role": "system", "content": msg.content})
            elif msg.role == "user":
                ollama_messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                entry = {"role": "assistant", "content": msg.content or ""}
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "function": {
                                "name": tc.name,
                                "arguments": tc.arguments,
                            }
                        }
                        for tc in msg.tool_calls
                    ]
                ollama_messages.append(entry)
            elif msg.role == "tool":
                ollama_messages.append({
                    "role": "tool",
                    "content": msg.content,
                })

        return ollama_messages

    def chat(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        system_prompt: Optional[str] = None,
    ) -> BrainResponse:
        """Send a chat request to Ollama with optional function calling."""
        client = self._get_client()

        ollama_messages = self._convert_messages_to_ollama(messages, system_prompt)
        ollama_tools = self._convert_tools_to_ollama(tools) if tools else None

        try:
            kwargs = {
                "model": self.model_name,
                "messages": ollama_messages,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            }
            if ollama_tools:
                kwargs["tools"] = ollama_tools

            response = client.chat(**kwargs)

            # Parse response
            text = response.get("message", {}).get("content", "")
            tool_calls = []

            raw_tool_calls = response.get("message", {}).get("tool_calls", [])
            for tc in raw_tool_calls:
                func = tc.get("function", {})
                args = func.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                tool_calls.append(ToolCall(
                    name=func.get("name", ""),
                    arguments=args,
                ))

            return BrainResponse(
                text=text,
                tool_calls=tool_calls,
                raw_response=response,
                model_used=self.model_name,
                tokens_used=response.get("eval_count", 0),
            )

        except Exception as e:
            error_msg = str(e)
            if "connection refused" in error_msg.lower():
                console.print("[red]❌ Ollama not running! Start it with: ollama serve[/red]")
            else:
                console.print(f"[red]❌ Ollama error: {error_msg}[/red]")

            return BrainResponse(
                text=f"Ollama error: {error_msg}. Make sure Ollama is running.",
                model_used=self.model_name,
            )

    def is_available(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            client = self._get_client()
            # Try to list models
            models = client.list()
            available = [m.get("name", "") for m in models.get("models", [])]
            model_base = self.model_name.split(":")[0]
            is_available = any(model_base in m for m in available)
            if not is_available:
                console.print(f"[yellow]⚠️  Model '{self.model_name}' not found. Pull it: ollama pull {self.model_name}[/yellow]")
            return is_available
        except Exception:
            return False

    def pull_model(self):
        """Pull/download the model if not available."""
        try:
            client = self._get_client()
            console.print(f"[cyan]📥 Pulling model: {self.model_name}...[/cyan]")
            client.pull(self.model_name)
            console.print(f"[green]✅ Model pulled: {self.model_name}[/green]")
        except Exception as e:
            console.print(f"[red]❌ Failed to pull model: {e}[/red]")
