"""
Victoria - OpenAI-Compatible Provider
Works with any API that follows the OpenAI chat completions format.
This covers: OpenRouter, Sarvam AI, Together AI, Groq, and many more.
Add any model from any provider with just a base_url and api_key!
"""

import json
from typing import Optional
from rich.console import Console

from victoria.brain.providers.base_provider import (
    BaseProvider, BrainResponse, Message, ToolCall, ToolDefinition
)

console = Console()


class OpenAICompatibleProvider(BaseProvider):
    """
    Universal provider for any OpenAI-compatible API.

    Supports:
      - OpenRouter (free and paid models)
      - Sarvam AI (Indic language models)
      - Together AI
      - Groq (ultra-fast inference)
      - Any OpenAI-compatible endpoint

    Just set base_url and api_key in config!
    """

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        if not self.base_url:
            raise ValueError("base_url is required for OpenAI-compatible providers")

    def _convert_tools(self, tools: list[ToolDefinition]) -> list:
        """Convert tools to OpenAI function calling format."""
        openai_tools = []
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

            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": parameters,
                },
            })
        return openai_tools

    def _convert_messages(self, messages: list[Message], system_prompt: Optional[str] = None) -> list:
        """Convert messages to OpenAI chat format."""
        openai_messages = []

        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            if msg.role == "system":
                openai_messages.append({"role": "system", "content": msg.content})
            elif msg.role == "user":
                openai_messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                entry = {"role": "assistant", "content": msg.content or ""}
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "id": tc.id or tc.name,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                openai_messages.append(entry)
            elif msg.role == "tool":
                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id or msg.name or "",
                    "content": msg.content,
                })

        return openai_messages

    def chat(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        system_prompt: Optional[str] = None,
    ) -> BrainResponse:
        """Send a chat request via OpenAI-compatible API."""
        import httpx

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # For OpenRouter, add extra headers
        if "openrouter" in self.base_url.lower():
            headers["HTTP-Referer"] = "https://victoria-assistant.local"
            headers["X-Title"] = "Victoria AI Assistant"

        payload = {
            "model": self.model_name,
            "messages": self._convert_messages(messages, system_prompt),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if tools:
            payload["tools"] = self._convert_tools(tools)
            payload["tool_choice"] = "auto"

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            # Parse response
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            text = message.get("content", "") or ""
            tool_calls = []

            raw_tool_calls = message.get("tool_calls", [])
            for tc in raw_tool_calls:
                func = tc.get("function", {})
                args_str = func.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(
                    name=func.get("name", ""),
                    arguments=args,
                    id=tc.get("id"),
                ))

            usage = data.get("usage", {})
            tokens = usage.get("total_tokens", 0)

            return BrainResponse(
                text=text,
                tool_calls=tool_calls,
                raw_response=data,
                model_used=self.model_name,
                tokens_used=tokens,
            )

        except httpx.HTTPStatusError as e:
            error_body = e.response.text[:500] if e.response else str(e)
            console.print(f"[red]❌ API error ({e.response.status_code}): {error_body}[/red]")
            return BrainResponse(
                text=f"API error: {error_body}",
                model_used=self.model_name,
            )
        except httpx.ConnectError:
            console.print(f"[red]❌ Cannot connect to {self.base_url}[/red]")
            return BrainResponse(
                text=f"Cannot connect to {self.base_url}",
                model_used=self.model_name,
            )
        except Exception as e:
            console.print(f"[red]❌ Provider error: {e}[/red]")
            return BrainResponse(
                text=f"Error: {str(e)}",
                model_used=self.model_name,
            )

    def is_available(self) -> bool:
        """Check if the API endpoint is reachable."""
        import httpx
        try:
            with httpx.Client(timeout=5.0) as client:
                # Try models endpoint
                url = f"{self.base_url.rstrip('/')}/models"
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                response = client.get(url, headers=headers)
                return response.status_code < 500
        except Exception:
            return False
