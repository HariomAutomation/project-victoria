"""
Victoria - Model Router (Pluggable AI Brain Controller)
Routes requests to the correct AI provider, manages tool execution loops,
and handles model switching at runtime.
"""

from typing import Optional
from rich.console import Console

from victoria.config import get_config
from victoria.brain.providers.base_provider import (
    BaseProvider, BrainResponse, Message
)
from victoria.brain.tools import ToolRegistry
from victoria.brain.persona import get_persona_engine
from victoria.brain.owner_memory import get_owner_vault
from victoria.brain.experience import get_experience_engine

console = Console()


# Provider registry - maps provider type to class
PROVIDER_MAP = {
    "gemini": "victoria.brain.providers.gemini_provider.GeminiProvider",
    "ollama": "victoria.brain.providers.ollama_provider.OllamaProvider",
    "openai_compatible": "victoria.brain.providers.openai_compatible_provider.OpenAICompatibleProvider",
}


def _import_provider_class(dotted_path: str):
    """Dynamically import a provider class."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class BrainRouter:
    """
    The central brain of Victoria.

    Responsibilities:
      - Route user messages to the active AI model
      - Execute tool calls returned by the model
      - Loop until the model gives a final text response
      - Switch models on command
      - Manage conversation context
      - Continuously learn task workflows & user corrections
    """

    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
        self._providers: dict[str, BaseProvider] = {}
        self._active_model: str = ""
        self._conversation: list[Message] = []
        self._max_tool_loops = 10  # Prevent infinite tool loops

        cfg = get_config()
        self._active_model = cfg.get_active_model_name()
        self._system_prompt = cfg.personality
        self.persona_engine = get_persona_engine()
        self.owner_vault = get_owner_vault()
        self.experience_engine = get_experience_engine()

    def _get_provider(self, model_name: Optional[str] = None) -> BaseProvider:
        """Get or create a provider instance for the given model."""
        if model_name is None:
            model_name = self._active_model

        if model_name not in self._providers:
            cfg = get_config()
            model_config = cfg.get_model_config(model_name)
            provider_type = model_config.get("provider", "gemini")

            if provider_type not in PROVIDER_MAP:
                raise ValueError(
                    f"Unknown provider type: {provider_type}. "
                    f"Available: {list(PROVIDER_MAP.keys())}"
                )

            provider_class = _import_provider_class(PROVIDER_MAP[provider_type])
            self._providers[model_name] = provider_class(model_config)

        return self._providers[model_name]

    def reload_provider(self, model_name: Optional[str] = None):
        """Invalidate cached provider instance so updated keys/endpoints take effect immediately."""
        if model_name:
            self._providers.pop(model_name, None)
            console.print(f"[cyan]🔄 Invalidated brain provider cache for: {model_name}[/cyan]")
        else:
            self._providers.clear()
            console.print("[cyan]🔄 Cleared all brain provider caches[/cyan]")

    def switch_model(self, model_name: str):
        """Switch the active AI model."""
        cfg = get_config()
        cfg.set_active_model(model_name)
        self._active_model = model_name
        self.reload_provider(model_name)
        console.print(f"[green]🧠 Brain switched to: {model_name}[/green]")

    def think(self, user_text: str) -> str:
        """
        Process a user message through the AI brain.

        This is the main entry point for the brain. It:
          1. Adds the user message to conversation history
          2. Recalls relevant local offline owner memories
          3. Sends to the active AI model with tool definitions
          4. If the model returns tool calls, executes them
          5. Feeds tool results back to the model
          6. Repeats until a final text response is given
          7. Learns and evolves from interaction locally
        """
        # Add user message to history
        self._conversation.append(Message(role="user", content=user_text))

        provider = self._get_provider()
        tool_definitions = self.tool_registry.get_definitions()

        # Inject Digital Twin persona directives into system prompt
        twin_directives = self.persona_engine.get_digital_twin_system_prompt()
        full_system_prompt = f"{self._system_prompt}\n\n{twin_directives}"

        # 🧠 Offline Memory Recall: Retrieve matching personal facts/preferences from local SQLite FTS5
        try:
            recalled_memories = self.owner_vault.get_relevant_context(user_text)
            if recalled_memories:
                full_system_prompt = f"{full_system_prompt}\n\n{recalled_memories}"
        except Exception as e:
            console.print(f"[yellow]⚠️ Memory recall notice: {e}[/yellow]")

        # 💡 Experiential Learning Recall: Retrieve past mastered workflows and learned rules for this task
        try:
            experience_context = self.experience_engine.get_relevant_experience(user_text)
            if experience_context:
                full_system_prompt = f"{full_system_prompt}\n\n{experience_context}"
        except Exception as e:
            console.print(f"[yellow]⚠️ Experience recall notice: {e}[/yellow]")

        final_text = ""
        tools_executed = []

        try:
            for loop_i in range(self._max_tool_loops):
                # Send to AI
                response: BrainResponse = provider.chat(
                    messages=self._conversation,
                    tools=tool_definitions,
                    system_prompt=full_system_prompt,
                )

                # If there are tool calls, execute them
                if response.tool_calls:
                    # Add assistant message with tool calls to history
                    self._conversation.append(Message(
                        role="assistant",
                        content=response.text or "",
                        tool_calls=response.tool_calls,
                    ))

                    # Execute each tool call
                    for tool_call in response.tool_calls:
                        # Record tool execution for experiential learning
                        tools_executed.append({
                            "name": tool_call.name,
                            "arguments": tool_call.arguments,
                        })

                        # Check for model switch (meta-tool)
                        if tool_call.name == "switch_ai_model":
                            new_model = tool_call.arguments.get("model_name", "")
                            try:
                                self.switch_model(new_model)
                                result = f"Successfully switched to {new_model}"
                            except Exception as e:
                                result = f"Error switching model: {str(e)}"
                        else:
                            # Check if dangerous and needs confirmation
                            cfg = get_config()
                            if self.tool_registry.is_dangerous(tool_call.name) and cfg.get("tools.confirm_dangerous", True):
                                # For now, execute anyway (confirmation handled by voice layer)
                                pass

                            result = self.tool_registry.execute(
                                tool_call.name,
                                tool_call.arguments,
                            )

                        # Add tool result to history
                        self._conversation.append(Message(
                            role="tool",
                            content=result,
                            tool_call_id=tool_call.id or tool_call.name,
                            name=tool_call.name,
                        ))

                    # Continue the loop to let the model process tool results
                    continue

                else:
                    # No tool calls - this is the final response
                    final_text = response.text
                    self._conversation.append(Message(
                        role="assistant",
                        content=final_text,
                    ))
                    break

        except Exception as e:
            console.print(f"[yellow]⚠️ AI Cloud error: {e}. Executing offline local engine...[/yellow]")
            offline_text = self._handle_offline_command(user_text)
            if offline_text:
                final_text = offline_text
            else:
                active_name = self._active_model
                final_text = (
                    f"Ji Malik, maine suna: '{user_text}'. "
                    f"AI cloud ({active_name}) se connect karne ke liye API key set karni hogi. "
                    f"Aap HUD screen par 'Connect AI Brain' button daba kar Gemini ya OpenRouter key jod sakte hain, "
                    f"ya .env file me set kar sakte hain. "
                    f"Tab tak volume, screenshot, apps, memory aur system control main offline bhi kar sakti hoon!"
                )

        if not final_text:
            final_text = "Ji Malik, maine aapka aadesh pura kar diya hai."

        # 📈 Self-evolution, Digital Twin, and Experiential Task Learning
        try:
            self.persona_engine.learn_from_interaction(user_text, final_text)
            self.experience_engine.learn_from_task(
                user_text=user_text,
                tools_called=tools_executed,
                assistant_text=final_text,
            )
        except Exception as e:
            console.print(f"[yellow]⚠️ Learning engine notice: {e}[/yellow]")

        # Trim conversation if too long
        self._trim_conversation()

        return final_text

    def _trim_conversation(self):
        """Keep conversation history within limits."""
        cfg = get_config()
        max_messages = cfg.get("memory.max_context_messages", 20)

        if len(self._conversation) > max_messages:
            # Keep the most recent messages
            self._conversation = self._conversation[-max_messages:]

    def clear_conversation(self):
        """Clear conversation history."""
        self._conversation = []
        console.print("[cyan]🧹 Conversation history cleared[/cyan]")

    def get_active_model_info(self) -> str:
        """Get info about the currently active model."""
        return f"Active model: {self._active_model}"

    def add_system_context(self, context: str):
        """Add additional system context to the conversation."""
        self._conversation.insert(0, Message(role="system", content=context))

    def _handle_offline_command(self, text: str) -> Optional[str]:
        """
        Handle common system commands locally and offline without requiring an external AI API.
        """
        t = text.lower().strip()

        # 1. Greetings & Presence Checks
        if any(w in t for w in ["kaise ho", "kya haal", "sun rahi ho", "kaha ho", "hello", "namaste", "namashkar"]):
            return "Ji Malik! Main hamesha active hoon, aapki awaz sun rahi hoon aur bilkul theek hoon. Kahiye, aaj kya kaam karna hai?"

        # 2. System Hardware Status (Battery, CPU, RAM)
        if any(w in t for w in ["status", "system", "battery", "ram", "cpu", "storage", "disk"]):
            try:
                res = self.tool_registry.execute("get_system_info", {})
                return f"Malik, system ka status yeh raha:\n{res}"
            except Exception as e:
                return f"System info nikalte samay error aaya: {e}"

        # 3. Audio & Volume Control
        if any(w in t for w in ["volume", "awaz", "sound", "aawaz", "mute", "shant"]):
            if any(w in t for w in ["badhao", "up", "tez", "increase"]):
                self.tool_registry.execute("set_volume", {"level": "85"})
                return "Malik, maine volume badha di hai."
            elif any(w in t for w in ["kam", "down", "dheere", "decrease", "ghatao"]):
                self.tool_registry.execute("set_volume", {"level": "45"})
                return "Malik, maine volume kam kar di hai."
            elif any(w in t for w in ["mute", "shant"]):
                self.tool_registry.execute("toggle_mute", {})
                return "Volume mute ho gaya hai Malik."
            else:
                return "Volume control tool ready hai Malik."

        # 4. Screenshots
        if any(w in t for w in ["screenshot", "screen shot", "photo", "screen capture"]):
            try:
                res = self.tool_registry.execute("take_screenshot", {})
                return f"Malik, maine screenshot le liya hai aur save kar diya hai: {res}"
            except Exception as e:
                return f"Screenshot lene me error aaya: {e}"

        # 5. Application Launching (Chrome, Terminal, Code, Calc)
        if any(w in t for w in ["kholo", "open", "launch", "chalao"]):
            for app in ["chrome", "terminal", "code", "firefox", "calculator", "files", "vlc"]:
                if app in t:
                    try:
                        self.tool_registry.execute("open_application", {"app_name": app})
                        return f"Ji Malik, {app} open kar diya hai."
                    except Exception as e:
                        return f"{app} launch karne me issue aaya: {e}"

        # 6. Memory & Owner Persona Recall
        if any(w in t for w in ["mera naam", "mere bare", "memory", "yaad", "vault", "malik", "profile"]):
            try:
                memories = self.owner_vault.get_relevant_context(t)
                if memories:
                    return f"Malik, mujhe aapke bare me yeh yaad hai:\n{memories}"
                else:
                    return "Aap mere maalik hain aur main sirf aapke orders follow karti hoon!"
            except Exception:
                pass

        # 7. Reverse Engineering & Clone Builder (Mor Luto REA Superpower)
        if any(w in t for w in ["reverse engineer", "teardown", "rea", "clone", "deconstruct"]):
            import re
            url_match = re.search(r'(https?://[^\s]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)', text)
            if url_match:
                target = url_match.group(1).rstrip(",.!?")
                if not target.startswith("http://") and not target.startswith("https://"):
                    target = "https://" + target
                try:
                    res = self.tool_registry.execute("reverse_engineer_anything", {"target": target, "target_type": "website"})
                    return f"Malik, maine '{target}' ka deep reverse engineering teardown complete kar liya hai! Architecture report save ho chuki hai aur main iska runnable clone preview generate kar sakti hoon."
                except Exception as e:
                    return f"Reverse engineering karte samay error aaya: {e}"
            else:
                return "Malik, kripya website ka URL ya app ka naam batayein jise reverse engineer karna hai (jaise 'reverse engineer stripe.com')."

        return None
