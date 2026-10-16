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

    def _convert_tools_to_gemini(self, tools: list[ToolDefinition]) -> list:
        """Convert our tool definitions to Gemini function declarations."""
        from google.genai import types

        function_declarations = []
        for tool in tools:
            properties = {}
            required = []

            for param in tool.parameters:
                prop = {"type": param.type.upper(), "description": param.description}
                if param.enum:
                    prop["enum"] = param.enum
                properties[param.name] = prop
                if param.required:
                    required.append(param.name)

            func_decl = types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        k: types.Schema(**v) for k, v in properties.items()
                    },
                    required=required,
                ) if properties else None,
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
                        parts.append(types.Part.from_function_call(
                            name=tc.name,
                            args=tc.arguments,
                        ))
                contents.append(types.Content(role="model", parts=parts))
            elif msg.role == "tool":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(
                        name=msg.name or "unknown",
                        response={"result": msg.content},
                    )],
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

        # Build config
        gen_config = types.GenerateContentConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )

        if system_prompt:
            gen_config.system_instruction = system_prompt

        if tools:
            gen_config.tools = self._convert_tools_to_gemini(tools)

        # Convert messages
        contents = self._convert_messages_to_gemini(messages)

        try:
            # Map legacy/hallucinated model names to valid Google GenAI models
            actual_model = self.model_name
            if actual_model in ["gemini", "gemini-2.5-flash"]:
                actual_model = "gemini-2.0-flash"
            elif actual_model in ["gemini_pro", "gemini-2.5-pro"]:
                actual_model = "gemini-1.5-pro"

            try:
                response = client.models.generate_content(
                    model=actual_model,
                    contents=contents,
                    config=gen_config,
                )
            except Exception as initial_err:
                err_str = str(initial_err).lower()
                # If model is not found, fallback to gemini-2.0-flash or gemini-1.5-flash
                if any(x in err_str for x in ["not_found", "not found", "404", "invalid_argument"]):
                    fallbacks = ["gemini-2.0-flash", "gemini-1.5-flash"]
                    recovered = False
                    for fb in fallbacks:
                        if fb == actual_model:
                            continue
                        try:
                            console.print(f"[yellow]⚠️ Model '{actual_model}' failed. Retrying with '{fb}'...[/yellow]")
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
                text=f"माफ़ कीजिए मालिक, Gemini से जुड़ने में त्रुटि आई: {str(e)}",
                model_used=self.model_name,
            )

    def is_available(self) -> bool:
        """Check if Gemini API key is configured."""
        if not self.api_key:
            console.print("[yellow]⚠️  GEMINI_API_KEY not set[/yellow]")
            return False
        import importlib.util
        return importlib.util.find_spec("google.genai") is not None
