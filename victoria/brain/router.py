"""
Victoria - Model Router (Pluggable AI Brain Controller)
Routes requests to the correct AI provider, manages tool execution loops,
and handles model switching at runtime.
"""

import re
from typing import Optional, Any, Callable
from rich.console import Console

from victoria.config import get_config
from victoria.brain.providers.base_provider import (
    BaseProvider, BrainResponse, Message
)
from victoria.brain.tools import ToolRegistry
from victoria.brain.persona import get_persona_engine
from victoria.brain.owner_memory import get_owner_vault
from victoria.brain.experience import get_experience_engine
from victoria.brain.daily_work_logger import get_daily_work_logger

console = Console()


# Provider registry - maps provider type to class
PROVIDER_MAP = {
    "gemini": "victoria.brain.providers.gemini_provider.GeminiProvider",
    "ollama": "victoria.brain.providers.ollama_provider.OllamaProvider",
    "openai_compatible": "victoria.brain.providers.openai_compatible_provider.OpenAICompatibleProvider",
    "opencode": "victoria.brain.providers.opencode_provider.OpenCodeProvider",
}


def _import_provider_class(dotted_path: str):
    """Dynamically import a provider class."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


# Prefixes with which providers report transport/API failures inside
# `BrainResponse.text`. Only these (or explicit connection errors) count as
# provider failures — a normal answer that merely mentions words like "token",
# "quota" or "503" must never be hijacked as an error.
_PROVIDER_ERROR_PREFIXES = (
    "API error:",
    "Gemini connection error:",
    "Ollama error:",
    "OpenCode error:",
    "OpenCode provider error:",
    "Provider error:",
)


def _response_is_provider_error(text: Any) -> bool:
    """True when a provider returned an error message as its response text."""
    if not text:
        return False
    s = str(text).strip()
    if s.startswith(_PROVIDER_ERROR_PREFIXES):
        return True
    return "connection error:" in s.lower()


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

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        if tool_registry is None:
            from victoria.brain.tools import build_tool_registry
            self.tool_registry = build_tool_registry()
        else:
            self.tool_registry = tool_registry
        self._providers: dict[str, BaseProvider] = {}
        self._active_model: str = ""
        self._conversation: list[Message] = []
        self._max_tool_loops = 10  # Prevent infinite tool loops

        # Host-provided confirmation hook for dangerous tools:
        #   confirm_callback(tool_name, arguments) -> bool
        # When None (HUD/MCP/headless contexts), dangerous tools are DENIED.
        self.confirm_callback: Optional[Callable[[str, dict], bool]] = None

        cfg = get_config()
        self._active_model = cfg.get_active_model_name()
        self._system_prompt = cfg.personality
        self.persona_engine = get_persona_engine()
        self.owner_vault = get_owner_vault()
        self.experience_engine = get_experience_engine()
        self.daily_work_logger = get_daily_work_logger()

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

    def _is_quota_or_rate_limit(self, err_or_text: Any) -> bool:
        """Check if an error or response text indicates quota, token limit, or rate limit exhaustion."""
        s = str(err_or_text).lower()
        keywords = [
            "429", "resource_exhausted", "resourceexhausted", "quota",
            "rate limit", "rate_limit", "rate-limit", "too many requests",
            "credits", "402", "payment required", "token limit", "token",
            "context_length_exceeded", "maximum context length",
            "503", "high demand", "overloaded", "temporarily unavailable",
            "daily free tier", "queue full", "unavailable for free", "not a valid model id",
        ]
        return any(k in s for k in keywords)

    def _confirm_dangerous_tool(self, tool_name: str, arguments: Any) -> bool:
        """
        Ask the host environment (voice loop / CLI) to confirm a dangerous tool.

        Fail-closed: if no confirmation callback is registered (HUD, MCP server,
        headless contexts), the dangerous tool is denied instead of silently run.
        """
        if self.confirm_callback is None:
            console.print(
                f"[yellow]🔒 Dangerous tool '{tool_name}' blocked: no confirmation channel available.[/yellow]"
            )
            return False
        try:
            return bool(self.confirm_callback(tool_name, arguments))
        except Exception as e:
            console.print(f"[yellow]⚠️ Confirmation failed for '{tool_name}': {e}[/yellow]")
            return False

    def _get_fallback_candidates(self) -> list[str]:
        """
        Return an ordered list of configured models that currently have a valid API key
        in .env or are local (Ollama). The current active model is always tried first.
        """
        cfg = get_config()
        all_models = cfg.get("brain.models", {})

        priority_order = [
            "gemini",
            "gemini_flash_lite",
            "opencode",
            "opencode_deepseek",
            "opencode_mimo",
            "opencode_nemotron",
            "opencode_glm",
            "openrouter",
            "nemotron_free",
            "cohere_coder_free",
            "liquid_free",
            "deepseek_free",
            "mimo_free",
            "qwen_coder_free",
            "openrouter_free",
            "sarvam",
            "groq",
            "openai_gpt4o",
            "local_fast",
        ]

        candidates = []
        for name in priority_order:
            m_cfg = all_models.get(name, {})
            if not m_cfg:
                continue
            provider = m_cfg.get("provider", "")
            if provider == "ollama":
                import importlib.util
                if importlib.util.find_spec("ollama") is not None:
                    candidates.append(name)
            elif provider == "opencode":
                import shutil
                from pathlib import Path
                if shutil.which("opencode") or Path("/usr/local/bin/opencode").exists():
                    if name not in candidates:
                        candidates.append(name)
            else:
                env_var = m_cfg.get("api_key_env")
                if env_var and cfg.get_api_key(env_var):
                    if name not in candidates:
                        candidates.append(name)

        if self._active_model in candidates:
            candidates.remove(self._active_model)
            candidates.insert(0, self._active_model)
        elif self._active_model:
            candidates.insert(0, self._active_model)

        return candidates

    def _get_tools_for_request(self, model_name: str, user_text: str) -> list:
        """
        Intelligently filter tools based on model context limits and user intent.
        Models with <= 32k context (like Sarvam AI, certain Ollama/OpenCode models)
        cannot take 207 MCP tools (~260k tokens).
        We supply all native Victoria tools (~71 tools, ~8k tokens).
        If the user specifically asks for reverse engineering, scraping, or REA,
        or if the model has a large context window (>100k, e.g. Gemini), we include MCP tools.
        """
        all_defs = self.tool_registry.get_definitions()
        
        # Check if query requests REA or web crawling (using word boundaries to avoid false positives like "create" or "area")
        wants_rea = bool(re.search(r"\b(?:reverse\s*engineer|teardown|rea|crawl|scrape|clone|deconstruct)\b", user_text, re.IGNORECASE))
        
        # Models known to have limited token budgets for tools
        limited_models = ["sarvam", "local_fast", "local_coder", "opencode", "opencode_mimo", "opencode_deepseek"]
        
        if (model_name in limited_models or model_name not in ["gemini", "gemini_pro", "gemini_flash_lite", "gemini_flash_latest"]) and not wants_rea:
            defs = [d for d in all_defs if not d.category.startswith("mcp")]
        else:
            defs = list(all_defs)

        # STRICT SCREENSHOT GUARD: Only supply screen analysis/screenshot tools if user explicitly mentions screen
        wants_screen = any(w in user_text.lower() for w in [
            "screen", "screenshot", "screen shot", "स्क्रीन", "स्क्रीनशॉट", "डिसप्ले", "display", "विंडो", "window"
        ])
        if not wants_screen:
            defs = [d for d in defs if d.name not in ["analyze_current_screen", "take_screenshot"]]

        return defs

    def think(self, user_text: str) -> str:
        """
        Process a user message through the AI brain.

        This is the main entry point for the brain. It:
          1. Adds the user message to conversation history
          2. Recalls relevant local offline owner memories
          3. Tries the active model, and if token limit or quota is exhausted,
             automatically switches to the next configured fallback model (e.g. Gemini <-> OpenRouter/Free)
          4. Executes any requested tools in a loop
          5. Returns the final natural text response
          6. Learns and evolves from interaction locally
        """
        # Add user message to history
        self._conversation.append(Message(role="user", content=user_text))

        # ⚡ Fast direct offline action check (Volume, Screen, Screenshots, Date/Time Queries)
        direct_res = self._handle_offline_command(user_text)
        if direct_res:
            final_text = self.persona_engine.filter_owner_speech(direct_res)
            try:
                self.daily_work_logger.auto_record_turn(
                    user_text=user_text,
                    assistant_text=final_text,
                    tools_used="direct_system_action",
                    model_used=self._active_model,
                )
            except Exception:
                pass
            return final_text

        # Inject Digital Twin persona directives into system prompt
        twin_directives = self.persona_engine.get_digital_twin_system_prompt()
        full_system_prompt = f"{self._system_prompt}\n\n{twin_directives}"

        # 📅 Daily Work Journal & Universal Model Resumption Context (Where We Left Off)
        try:
            daily_context = self.daily_work_logger.get_continuation_context(user_text)
            if daily_context:
                full_system_prompt = f"{full_system_prompt}\n\n{daily_context}"
        except Exception as e:
            console.print(f"[yellow]⚠️ Daily work context notice: {e}[/yellow]")

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
        candidates = self._get_fallback_candidates()
        last_error = None

        for candidate_model in candidates:
            conversation_snapshot = list(self._conversation)
            attempt_tools = []
            try:
                if candidate_model != self._active_model:
                    console.print(f"[yellow]🔄 Auto-switching AI Brain from '{self._active_model}' to fallback '{candidate_model}'...[/yellow]")
                    self.switch_model(candidate_model)
                    get_config().set_active_model(candidate_model, persist=True)

                provider = self._get_provider(candidate_model)
                model_succeeded = False
                active_tools = self._get_tools_for_request(candidate_model, user_text)

                for loop_i in range(self._max_tool_loops):
                    # Send to AI
                    response: BrainResponse = provider.chat(
                        messages=self._conversation,
                        tools=active_tools,
                        system_prompt=full_system_prompt,
                    )

                    # Fail over only on REAL provider error messages. A normal answer
                    # that merely mentions "token", "quota", "503" etc. must pass through.
                    resp_str = str(response.text or "")
                    if _response_is_provider_error(resp_str):
                        if self._is_quota_or_rate_limit(resp_str):
                            console.print("[yellow]⚠️ Provider quota/limit issue detected. Trying next available model...[/yellow]")
                        raise RuntimeError(resp_str)

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
                            attempt_tools.append({
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
                                cfg = get_config()
                                if (
                                    self.tool_registry.is_dangerous(tool_call.name)
                                    and cfg.get("tools.confirm_dangerous", True)
                                    and not self._confirm_dangerous_tool(tool_call.name, tool_call.arguments)
                                ):
                                    result = (
                                        f"⛔ '{tool_call.name}' एक संवेदनशील (dangerous) टूल है और मालिक की पुष्टि नहीं मिली, "
                                        "इसलिए इसे execute नहीं किया गया।"
                                    )
                                else:
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
                        model_succeeded = True
                        tools_executed.extend(attempt_tools)
                        break

                if model_succeeded:
                    break

            except Exception as e:
                last_error = e
                # Rollback conversation history to avoid corrupted half-states
                self._conversation = conversation_snapshot
                console.print(f"[yellow]⚠️ Model '{candidate_model}' encountered error ({e}). Auto-switching to next candidate...[/yellow]")
                continue

        if not final_text:
            console.print(f"[yellow]⚠️ All AI Cloud models exhausted or failed ({last_error}). Executing offline local engine...[/yellow]")
            offline_text = self._handle_offline_command(user_text)
            if offline_text:
                final_text = offline_text
            else:
                active_name = self._active_model
                final_text = (
                    f"जी हरिओम, मैंने सुना: '{user_text}'। "
                    f"AI क्लाउड ({active_name}) से कनेक्ट करने के लिए API key सेट करनी होगी। "
                    f"आप HUD स्क्रीन पर 'Connect AI Brain' बटन दबा कर Gemini या OpenRouter key जोड़ सकते हैं, "
                    f"या .env फाइल में सेट कर सकते हैं। "
                    f"तब तक वॉल्यूम, स्क्रीनशॉट, ऐप्स, मेमोरी और सिस्टम कंट्रोल मैं ऑफ़लाइन भी कर सकती हूँ!"
                )

        if not final_text:
            final_text = "जी हरिओम, मैंने आपका कार्य पूरा कर दिया है।"

        # Ensure strict respect to Hariom across all models (eliminate 'मालिक')
        final_text = self.persona_engine.filter_owner_speech(final_text)

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

        # 📅 Auto-record turn in daily work journal & update 'Where We Left Off' checkpoint
        try:
            tools_str = ", ".join([t["name"] for t in tools_executed]) if tools_executed else ""
            self.daily_work_logger.auto_record_turn(
                user_text=user_text,
                assistant_text=final_text,
                tools_used=tools_str,
                model_used=self._active_model,
            )
        except Exception as e:
            console.print(f"[yellow]⚠️ Daily work auto-record notice: {e}[/yellow]")

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
            # Never start with orphaned tool results: providers expect a preceding
            # assistant(tool_calls) message and will reject a leading tool message.
            while self._conversation and self._conversation[0].role == "tool":
                self._conversation.pop(0)

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

        # 00. Security On / Reboot Lock / Data Deletion Protection Inquiries & Enforcement
        # e.g. "reboot ka lock karo", "ye reboot samjh rha hai", "security on karo", "data na delete kar de"
        security_lock_triggers = [
            "reboot ka lock", "reboot lock", "lock karo reboot", "reboot mat karo",
            "ye reboot samjh", "reboot samjh rha", "reboot samajh", "reboot na kare",
            "data na delete", "data delete na", "security on karo", "security on kar do",
            "kuch bhi remove karne se", "kuch bhi delete karne se", "remove karne se phele",
            "remove karne se pehle", "delete karne se pehle", "delete karne se phele",
            "रीबूट लॉक", "रीबूट का लॉक", "रीबूट मत समझो", "रीबूट मत करो", "डेटा डिलीट",
            "सिक्योरिटी ऑन करो", "सुरक्षा ऑन करो", "रिमूव करने से पहले", "डेटा सुरक्षा"
        ]
        if any(w in t for w in security_lock_triggers):
            return (
                "जी हरिओम! आपके सिस्टम पर रीबूट और शटडाउन का परमानेंट सिक्योरिटी लॉक सक्रिय है। "
                "विक्टोरिया कभी भी आपके ऑपरेटिंग सिस्टम को रीबूट या बंद नहीं करेगी। "
                "साथ ही सिस्टम से किसी भी प्रकार की फ़ाइल या डेटा को हटाने (remove/delete) पर सख्त डेटा सुरक्षा लॉक लागू कर दिया गया है। "
                "आपका डेटा 100% सुरक्षित है। जब भी आप 'रीस्टार्ट' कहेंगे, केवल विक्टोरिया असिस्टेंट ही रीफ्रेश होगी।"
            )

        # 00b. System Reboot & Shutdown Prohibited Lock
        # e.g. "system reboot", "laptop reboot karo", "shutdown karo", "power off"
        os_reboot_triggers = [
            "system reboot", "laptop reboot", "pc reboot", "computer reboot", "reboot system", "reboot laptop",
            "सिस्टम रीबूट", "लैपटॉप रीबूट", "कंप्यूटर रीबूट", "पीसी रीबूट", "रीबूट करो",
            "system shutdown", "laptop shutdown", "shutdown karo", "power off", "poweroff",
            "सिस्टम शटडाउन", "लैपटॉप शटडाउन", "कंप्यूटर शटडाउन", "शटडाउन करो", "सिस्टम बंद करो", "लैपटॉप बंद करो"
        ]
        if any(w in t for w in os_reboot_triggers):
            return (
                "🚫 सुरक्षा लॉक सक्रिय: हरिओम जी, आपके सिस्टम पर रीबूट और शटडाउन पूर्णतः लॉक (प्रतिबंधित) है "
                "ताकि आपका कोई भी डेटा या कार्य नष्ट न हो। विक्टोरिया कभी भी आपके कंप्यूटर को रीबूट या बंद नहीं करेगी।"
            )

        # 00c. Victoria Assistant Restart & Refresh — only an explicit restart COMMAND
        # reloads the assistant. A question that merely mentions the word "restart"
        # (e.g. "restart ka matlab kya hai") must fall through to the AI.
        restart_word = re.search(r"\b(restart|relaunch|re-launch)\b", t) or re.search(r"(रीस्टार्ट|रिलांच)", t)
        restart_command = any(w in t for w in ["karo", "kar do", "kar de", "करो", "कर दो", "victoria", "असिस्टेंट", "assistant", "please", "plz"])
        restart_question = any(q in t for q in ["kya", "kyun", "kyu", "kaise", "kab", "matlab", "why", "what", "how", "meaning", "batao", "samjhao", "बताओ", "समझाओ"])
        if restart_word and (restart_command or len(t.split()) <= 2) and not restart_question:
            self.reload_provider()
            self._conversation.clear()
            return (
                "जी हरिओम! विक्टोरिया असिस्टेंट को सफलतापूर्वक रीस्टार्ट और रीफ्रेश कर दिया गया है। "
                "आपके सिस्टम पर रीबूट लॉक और डेटा सुरक्षा लॉक सक्रिय है।"
            )

        # 0. Daily Work Journal & Continuity ("जहाँ काम छोड़ा था", "हम क्या कर रहे थे?")
        if any(w in t for w in ["kaha chhoda", "jaha chhoda", "left off", "pichla kaam", "kal ka kaam", "chhodha tha"]):
            try:
                ckpt = self.daily_work_logger.get_last_checkpoint()
                if ckpt:
                    return (
                        f"जी हरिओम! पिछली बार हम '{ckpt.get('last_task')}' पर काम कर रहे थे। "
                        f"स्थिति: {ckpt.get('where_we_left_off')}। "
                        f"अगले कदम: {ckpt.get('next_planned_steps')}। "
                        f"क्या मैं इसे यहीं से आगे जारी रखूँ?"
                    )
            except Exception:
                pass

        # 0b. Date & Time Work Timeline Inquiry (e.g. "16 तारीख को 2:30 बजे क्या किया था?", "3 बजे क्या हुआ था?")
        if any(w in t for w in ["kya kiya tha", "kya hua tha", "kya kaam hua tha", "kya kar rahe the", "kya kiya", "baje kya", "tareekh ko", "tarikh ko"]):
            try:
                res = self.daily_work_logger.query_work_by_date_time(text)
                if res and res.get("found"):
                    return res.get("speech")
            except Exception:
                pass

        # 1. Greetings & Presence Checks
        if any(w in t for w in ["kaise ho", "kya haal", "sun rahi ho", "kaha ho", "hello", "namaste", "namashkar"]):
            return "जी हरिओम! मैं हमेशा सक्रिय हूँ, आपकी आवाज़ सुन रही हूँ और बिल्कुल ठीक हूँ। बताइए, आज क्या काम करना है?"

        # 2. System Hardware Status (Battery, CPU, RAM) — only for explicit status queries
        hardware_terms = ["battery", "ram", "cpu", "storage", "disk", "system", "hardware", "gpu", "temperature", "temp", "memory", "बैटरी", "रैम", "सीपीयू", "स्टोरेज", "डिस्क", "सिस्टम", "तापमान", "मेमोरी"]
        status_queries = ["status", "kitna", "kitni", "kitne", "check", "batao", "bata do", "info", "usage", "space", "percent", "%", "how much", "बताओ", "जांच", "चेक", "कितना", "कितनी", "स्थिति", "स्टेटस"]
        concept_question = ["kya", "kaise", "kyun", "matlab", "what is", "why", "how", "क्या", "कैसे", "मतलब"]
        if (
            any(w in t for w in hardware_terms)
            and any(w in t for w in status_queries)
            and not any(q in t for q in concept_question)
            and not any(w in t for w in ["lock", "unlock"])
        ):
            try:
                res = self.tool_registry.execute("get_system_info", {})
                return f"हरिओम जी, सिस्टम का स्टेटस यह रहा:\n{res}"
            except Exception as e:
                return f"System info निकालते समय समस्या आई: {e}"

        # 2b. Voice Biometric Desktop Lock & Unlock
        unlock_triggers = [
            "unlock", "lock kholo", "unlock karo", "screen kholo", "lock hatao", "lock khol do",
            "screen unlock", "system unlock", "lock khol",
            "लॉक खोलो", "अनलॉक करो", "स्क्रीन खोलो", "अनलॉक", "लॉक खोल दो", "अनलॉक कर दो",
            "स्क्रीन अनलॉक", "सिस्टम अनलॉक", "स्क्रीन का लॉक खोलो", "सिस्टम का लॉक खोलो",
            "स्क्रीन का लॉक खोल दो", "सिस्टम का लॉक खोल दो", "लॉक हटाओ", "सिस्टम खोलो"
        ]
        if any(w in t for w in unlock_triggers):
            from victoria.tools.system_lock import unlock_system_by_voice
            res = unlock_system_by_voice()
            return res.get("message", "जी हरिओम! आपकी आवाज़ सत्यापित हो गई है। सिस्टम स्क्रीन अनलॉक कर दी गई है।")

        lock_triggers = [
            "lock screen", "screen lock", "system lock", "lock karo", "lock kar do", "pc lock", "laptop lock",
            "स्क्रीन लॉक करो", "सिस्टम लॉक करो", "स्क्रीन लॉक", "सिस्टम लॉक", "स्क्रीन लॉक कर दो",
            "सिस्टम लॉक कर दो", "सिस्टम को लॉक करो", "स्क्रीन को लॉक करो", "कंप्यूटर लॉक करो", "पीसी लॉक करो",
            "लॉक कर दो", "लॉक करो"
        ]
        if any(w in t for w in lock_triggers):
            from victoria.tools.system_lock import lock_system
            return lock_system()

        # 3. Audio & Volume Control
        if any(w in t for w in ["volume", "awaz", "sound", "aawaz", "mute", "shant"]):
            if any(w in t for w in ["badhao", "up", "tez", "increase"]):
                self.tool_registry.execute("set_volume", {"level": "85"})
                return "जी हरिओम, मैंने वॉल्यूम (volume) बढ़ा दी है।"
            elif any(w in t for w in ["kam", "down", "dheere", "decrease", "ghatao"]):
                self.tool_registry.execute("set_volume", {"level": "45"})
                return "जी हरिओम, मैंने वॉल्यूम (volume) कम कर दी है।"
            elif any(w in t for w in ["mute", "shant"]):
                self.tool_registry.execute("toggle_mute", {})
                return "वॉल्यूम (volume) म्यूट हो गया है हरिओम जी।"
            else:
                return "वॉल्यूम (volume) कंट्रोल टूल तैयार है हरिओम जी।"

        # 3a. Media / Music Playback Control (Instant offline execution)
        if any(w in t for w in ["gana", "music", "song", "gaana", "spotify", "playback", "प्लेबैक", "गाना", "गाने", "गीत", "म्यूजिक"]):
            if any(w in t for w in ["band", "roko", "pause", "stop", "chup", "बंद", "रोको", "पॉज", "रोक", "रोकना"]):
                try:
                    from victoria.tools.media_player import pause_media
                    pause_media()
                    return "जी हरिओम, गाना रोक दिया गया है।"
                except Exception as e:
                    return f"गाना रोकने में समस्या आई: {e}"
            elif any(w in t for w in ["chalao", "play", "resume", "shuru", "start", "चलाओ", "शुरू", "बजाओ", "प्ले"]):
                try:
                    from victoria.tools.media_player import play_media
                    play_media()
                    return "जी हरिओम, गाना शुरू कर दिया गया है।"
                except Exception as e:
                    return f"गाना शुरू करने में समस्या आई: {e}"
            elif any(w in t for w in ["next", "agla", "change", "badlo", "अगला", "बदलो"]):
                try:
                    from victoria.tools.media_player import next_media
                    next_media()
                    return "जी हरिओम, अगला गाना लगा दिया है।"
                except Exception as e:
                    return f"अगला गाना लगाने में समस्या आई: {e}"

        # 3b. Instant Live Weather Shortcut (e.g. "वाराणसी का मौसम", "weather")
        if any(w in t for w in ["mausam", "weather", "tapman", "taapman", "temperature", "मौसम", "तापमान"]):
            try:
                from victoria.tools.weather_tool import get_weather
                city = "Varanasi"
                for c in ["delhi", "mumbai", "kolkata", "chennai", "lucknow", "varanasi", "bangalore", "noida", "jaipur"]:
                    if c in t:
                        city = c.title()
                        break
                return get_weather(city)
            except Exception:
                pass

        # 4. Multimodal Screen Analysis - ONLY when explicitly asked "what is on screen / look at screen"
        screen_check_phrases = [
            "screen dekho", "screen check", "screen par kya chal raha", "screen par kya chal rha",
            "screen par kya hai", "screen par kya dikh raha", "meri screen dekho",
            "what is on screen", "what's on my screen", "what is on the screen",
            "read my screen", "look at my screen", "screen samjhao", "screen padho",
            "स्क्रीन देखो", "स्क्रीन पर क्या चल रहा है", "स्क्रीन पर क्या चल रहा",
            "स्क्रीन पर क्या है", "स्क्रीन पर क्या दिख रहा है", "स्क्रीन पर क्या दिख रहा",
            "स्क्रीन चेक करो", "स्क्रीन समझाओ", "मेरी स्क्रीन देखो", "स्क्रीन पढ़ो"
        ]
        screen_excluded = ["lock", "unlock", "off", "on", "brightness", "volume", "sound", "band", "kholo", "खोलो", "अनलॉक", "लॉक", "बंद"]
        if any(p in t for p in screen_check_phrases) and not any(ex in t for ex in screen_excluded):
            try:
                from victoria.tools.desktop_inspector import get_desktop_screen_overview
                return get_desktop_screen_overview()
            except Exception as e:
                return f"स्क्रीन का विश्लेषण करते समय समस्या आई: {e}"

        if any(w in t for w in ["video analyze", "video analysis", "video samjhao", "iss video me"]):
            m = re.search(r'([/\w\.-]+\.(?:mp4|mkv|avi|webm|mov))', text, re.IGNORECASE)
            if m:
                vpath = m.group(1)
                try:
                    return self.tool_registry.execute("analyze_video", {"video_path": vpath, "question": text})
                except Exception as e:
                    return f"वीडियो विश्लेषण करते समय समस्या आई: {e}"
            else:
                return "हरिओम जी, कृपया वीडियो फ़ाइल का पाथ बताएं (जैसे: 'analyze video /path/to/video.mp4')।"

        if any(w in t for w in ["image analyze", "photo analyze", "image samjhao", "photo samjhao", "iss photo me", "iss image me"]):
            m = re.search(r'([/\w\.-]+\.(?:png|jpg|jpeg|webp|bmp|gif|svg))', text, re.IGNORECASE)
            if m:
                ipath = m.group(1)
                try:
                    return self.tool_registry.execute("analyze_image", {"image_path": ipath, "question": text})
                except Exception as e:
                    return f"इमेज विश्लेषण करते समय समस्या आई: {e}"
            else:
                return "हरिओम जी, कृपया इमेज फ़ाइल का पाथ बताएं (जैसे: 'analyze image /path/to/photo.jpg')।"

        # 5. Explicit Screenshot Taking - ONLY when explicitly commanded to capture/take screenshot
        screenshot_triggers = [
            "take screenshot", "take a screenshot", "capture screen", "capture the screen",
            "screenshot lo", "screen shot lo", "screenshot kheencho", "screenshot khincho",
            "screenshot le lo", "screen shot le lo", "save screenshot",
            "स्क्रीनशॉट लो", "स्क्रीनशॉट ले लो", "स्क्रीनशॉट खींचो", "स्क्रीन कैप्चर करो",
            "स्क्रीन का स्क्रीनशॉट लो"
        ]
        if any(w in t for w in screenshot_triggers):
            try:
                res = self.tool_registry.execute("take_screenshot", {})
                return f"जी हरिओम! स्क्रीनशॉट ले लिया गया है: {res}"
            except Exception as e:
                return f"Screenshot लेने में त्रुटि आई: {e}"

        # 5. Application Launching (Chrome, Terminal, Code, Calc)
        app_question = any(q in t for q in ["kya", "kaise", "kyun", "kyu", "matlab", "what", "why", "how", "meaning", "बताओ", "क्या", "कैसे"])
        if any(w in t for w in ["kholo", "open", "launch", "chalao"]) and not app_question:
            for app in ["chrome", "terminal", "code", "firefox", "calculator", "files", "vlc"]:
                if re.search(rf"(?<!\w){app}(?!\w)", t):
                    try:
                        self.tool_registry.execute("open_application", {"app_name": app})
                        return f"जी हरिओम, {app} खोल दिया गया है।"
                    except Exception as e:
                        return f"{app} शुरू करने में त्रुटि आई: {e}"

        # 6. Memory & Owner Persona Recall — only explicit "about me" queries
        memory_triggers = [
            "mera naam", "mere bare", "mere baare", "mere baare mein", "about me", "my profile",
            "meri profile", "meri memory", "mere preferences", "meri pasand", "meri napasand",
            "kya yaad hai", "mujhe kya yaad", "मेरा नाम", "मेरे बारे", "मेरी प्रोफाइल", "मेरी पसंद", "मुझे क्या याद",
        ]
        if any(w in t for w in memory_triggers):
            try:
                memories = self.owner_vault.get_relevant_context(t)
                if memories:
                    return f"हरिओम जी, मुझे आपके बारे में यह याद है:\n{memories}"
                else:
                    return "आप हरिओम जी हैं और मैं आपकी अपनी पर्सनल AI असिस्टेंट विक्टोरिया हूँ!"
            except Exception:
                pass

        # 7. Reverse Engineering & Clone Builder (Mor Luto REA Superpower)
        # "clone" only counts in a web-target context, so "git clone ..." questions
        # and ordinary clone talk never trigger a teardown.
        rea_word = re.search(r"\b(?:reverse\s*engineer|teardown|rea|deconstruct)\b", t, re.IGNORECASE)
        clone_web = re.search(r"\bclone\b", t, re.IGNORECASE) and any(
            w in t for w in ["website", "site", "web", "frontend", "app", "page", "url"]
        )
        if rea_word or clone_web:
            url_match = re.search(r'(https?://[^\s]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)', text)
            if url_match:
                target = url_match.group(1).rstrip(",.!?")
                if not target.startswith("http://") and not target.startswith("https://"):
                    target = "https://" + target
                try:
                    res = self.tool_registry.execute("reverse_engineer_anything", {"target": target, "target_type": "website"})
                    return f"हरिओम जी, मैंने '{target}' का डीप रिवर्स इंजीनियरिंग टियरडाउन पूरा कर लिया है! आर्किटेक्चर रिपोर्ट सुरक्षित हो चुकी है।"
                except Exception as e:
                    return f"रिवर्स इंजीनियरिंग करते समय त्रुटि आई: {e}"
            else:
                return "हरिओम जी, कृपया उस वेबसाइट का URL या ऐप का नाम बताएं जिसे रिवर्स इंजीनियर करना है।"

        return None
