"""
Victoria - Google Gemini Provider
Uses the official google-genai SDK for Gemini 2.5 Flash/Pro with function calling.
"""

from typing import Optional
from rich.console import Console

from victoria.brain.providers.base_provider import (
    BaseProvider, BrainResponse, Message, ToolCall, ToolDefinition
)

console = Console()


class GeminiProvider(BaseProvider):
    """
    Google Gemini AI Provider.
    Supports Gemini 2.5 Flash, 2.5 Pro, and other Gemini models.
    Uses the google-genai SDK with native function calling.
    """

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self._client = None

    def _get_client(self):
        """Lazy-load the Gemini client."""
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                console.print(f"[green]✅ Gemini client initialized: {self.model_name}[/green]")
            except ImportError:
                console.print("[red]❌ google-genai not installed. pip install google-genai[/red]")
                raise
        return self._client

    @staticmethod
    def _json_schema_to_gemini(schema: dict):
        """Recursively convert a JSON Schema fragment into a Gemini types.Schema."""
        from google.genai import types

        if not isinstance(schema, dict):
            return types.Schema(type="STRING")

        raw_type = schema.get("type") or "object"
        if isinstance(raw_type, list):
            raw_type = raw_type[0] if raw_type else "string"
        t = str(raw_type).upper()
        if t not in {"OBJECT", "ARRAY", "STRING", "NUMBER", "INTEGER", "BOOLEAN"}:
            t = "STRING"

        kwargs: dict = {}
        if schema.get("description"):
            kwargs["description"] = str(schema["description"])[:1024]
        if schema.get("enum"):
            kwargs["enum"] = [str(e) for e in schema["enum"]]

        if t == "OBJECT":
            props = schema.get("properties") or {}
            if props:
                kwargs["properties"] = {
                    k: GeminiProvider._json_schema_to_gemini(v) for k, v in props.items()
                }
            if schema.get("required"):
                kwargs["required"] = list(schema["required"])
        elif t == "ARRAY":
            items = schema.get("items")
            if isinstance(items, dict):
                kwargs["items"] = GeminiProvider._json_schema_to_gemini(items)

        return types.Schema(type=t, **kwargs)

    def _convert_tools_to_gemini(self, tools: list[ToolDefinition]) -> list:
        """Convert our tool definitions to Gemini function declarations."""
        from google.genai import types

        function_declarations = []
        for tool in tools:
            if getattr(tool, "raw_schema", None):
                params_schema = self._json_schema_to_gemini(tool.raw_schema)
            else:
                properties = {}
                required = []

                for param in tool.parameters:
                    prop = {"type": param.type.upper(), "description": param.description}
                    if param.enum:
                        prop["enum"] = param.enum
                    properties[param.name] = prop
                    if param.required:
                        required.append(param.name)

                params_schema = types.Schema(
                    type="OBJECT",
                    properties={
                        k: types.Schema(**v) for k, v in properties.items()
                    },
                    required=required,
                ) if properties else None

            func_decl = types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=params_schema,
            )
            function_declarations.append(func_decl)

        return [types.Tool(function_declarations=function_declarations)]

    def _convert_messages_to_gemini(self, messages: list[Message]) -> list:
        """Convert our messages to Gemini content format."""
        from google.genai import types

        contents = []
        for msg in messages:
            if msg.role == "system":
                continue  # System prompt handled separately
            elif msg.role == "user":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=msg.content)],
                ))
            elif msg.role == "assistant":
                parts = [types.Part.from_text(text=msg.content)] if msg.content else []
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        # Reconstructing raw from_function_call without thought_signature throws 400 INVALID_ARGUMENT
                        # in Gemini 2.0/3.0. Passing tool executions as descriptive context retains memory cleanly:
                        parts.append(types.Part.from_text(text=f"[Executed Action: {tc.name} with {tc.arguments}]"))
                if not parts:
                    parts = [types.Part.from_text(text="...")]
                contents.append(types.Content(role="model", parts=parts))
            elif msg.role == "tool":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=f"[Action Result for {msg.name or 'tool'}: {msg.content}]")],
                ))

        return contents

    def chat(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        system_prompt: Optional[str] = None,
    ) -> BrainResponse:
        """Send a chat request to Gemini with function calling support."""
        from google.genai import types

        client = self._get_client()

        # Build config (avoid thinking_budget=0 which causes 400 on flash-lite / flash-latest)
        gen_config = types.GenerateContentConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )

        # Map legacy aliases to official Google GenAI models, preserving latest models
        actual_model = self.model_name
        if actual_model == "gemini":
            actual_model = "gemini-3.8-flash"
        elif actual_model in ["gemini_4", "gemini-4"]:
            actual_model = "gemini-4-argon"
        elif actual_model in ["gemini_38", "gemini-3.8-flash"]:
            actual_model = "gemini-3.8-flash"
        elif actual_model in ["gemini_36", "gemini-3.6-flash"]:
            actual_model = "gemini-3.6-flash"
        elif actual_model in ["gemini_pro", "gemini-2.5-pro"]:
            actual_model = "gemini-3.1-pro-preview"
        elif actual_model in ["gemini_flash_lite", "gemini-3.5-flash-lite"]:
            actual_model = "gemini-3.5-flash-lite"

        # Explicitly instruct the model of its exact version so it never hallucinates legacy models like 2.5
        active_instruction = system_prompt or ""
        if "[AI Model Notice" not in active_instruction:
            active_instruction += f"\n[AI Model Notice: You are powered by Google {actual_model} (Project Victoria AI Brain). State your exact model name when asked]."
        gen_config.system_instruction = active_instruction

        if tools:
            gen_config.tools = self._convert_tools_to_gemini(tools)

        # Convert messages
        contents = self._convert_messages_to_gemini(messages)

        try:
            try:
                response = client.models.generate_content(
                    model=actual_model,
                    contents=contents,
                    config=gen_config,
                )
            except Exception as initial_err:
                err_str = str(initial_err).lower()
                # If model is unavailable, rate-limited or not found, fallback to next reliable latest Gemini model
                if any(x in err_str for x in ["not_found", "not found", "404", "invalid_argument", "503", "unavailable", "resource_exhausted", "429", "high demand"]):
                    fallbacks = [
                        "gemini-3.8-flash",
                        "gemini-4-argon",
                        "gemini-3.6-flash",
                        "gemini-3.5-flash",
                        "gemini-3.5-flash-lite",
                        "gemini-flash-latest",
                        "gemini-3.1-pro-preview",
                    ]
                    recovered = False
                    for fb in fallbacks:
                        if fb == actual_model:
                            continue
                        try:
                            console.print(f"[yellow]⚠️ Model '{actual_model}' failed ({initial_err}). Retrying with '{fb}'...[/yellow]")
                            gen_config.system_instruction = (system_prompt or "") + f"\n[AI Model Notice: You are powered by Google {fb} (Project Victoria AI Brain). State your exact model name when asked]."
                            response = client.models.generate_content(
                                model=fb,
                                contents=contents,
                                config=gen_config,
                            )
                            self.model_name = fb
                            actual_model = fb
                            recovered = True
                            break
                        except Exception:
                            continue
                    if not recovered:
                        raise initial_err
                else:
                    raise initial_err

            # Parse response
            text_parts = []
            tool_calls = []

            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if part.text:
                        text_parts.append(part.text)
                    elif part.function_call:
                        fc = part.function_call
                        tool_calls.append(ToolCall(
                            name=fc.name,
                            arguments=dict(fc.args) if fc.args else {},
                            id=fc.name,
                        ))

            text = " ".join(text_parts).strip()
            tokens = getattr(response, 'usage_metadata', None)
            token_count = 0
            if tokens:
                token_count = getattr(tokens, 'total_token_count', 0)

            return BrainResponse(
                text=text,
                tool_calls=tool_calls,
                raw_response=response,
                model_used=actual_model,
                tokens_used=token_count,
            )

        except Exception as e:
            console.print(f"[red]❌ Gemini API error: {e}[/red]")
            return BrainResponse(
                text=f"Gemini connection error: {str(e)}",
                model_used=self.model_name,
            )

    def is_available(self) -> bool:
        """Check if Gemini API key is configured."""
        if not self.api_key:
            console.print("[yellow]⚠️  GEMINI_API_KEY not set[/yellow]")
            return False
        import importlib.util
        return importlib.util.find_spec("google.genai") is not None
