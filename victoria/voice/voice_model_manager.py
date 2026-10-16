"""
Victoria - Voice Model Manager & Interactive Model Switcher
Handles conversational model inquiries, voice-driven AI brain selection,
and seamless switching between OpenCode (DeepSeek, Xiaomi MiMo, Nemotron, GLM)
and cloud providers (Gemini, OpenRouter).
"""

import re
from typing import Optional, Tuple

FRIENDLY_NAMES = {
    "opencode": "OpenCode",
    "opencode_deepseek": "DeepSeek V4.1 Flash",
    "opencode_mimo": "Xiaomi MiMo",
    "opencode_nemotron": "NVIDIA Nemotron 3.5",
    "opencode_glm": "GLM 5.3 Flash",
    "gemini": "Google Gemini",
    "gemini_flash_lite": "Gemini Flash Lite",
    "openrouter": "OpenRouter",
    "local_fast": "Ollama Local",
    "sarvam": "Sarvam AI",
}

MODEL_PATTERNS = [
    # Google Gemini (strict: bare "google"/"flash"/"lite"/"3.5" must NOT switch models)
    (r"(gemini|जेमिनी|गेमिनी|gemeni|google\s*gemini)", "gemini", "Google Gemini Flash"),
    # DeepSeek
    (r"(deep\s*seek|डीप\s*सीक|दीप\s*सीक|डिप\s*सिक)", "opencode_deepseek", "DeepSeek V4.1 Flash"),
    # Xiaomi MiMo
    (r"(\bmi\s*mo\b|मीमो|मईमो|xiaomi|शाओमी)", "opencode_mimo", "Xiaomi MiMo"),
    # OpenCode General
    (r"(open\s*code|ओपन\s*कोड)", "opencode", "OpenCode"),
    # NVIDIA Nemotron
    (r"(nemo\s*tron|नेमोट्रॉन|nvidia\s+(?:nemotron|ai|model))", "opencode_nemotron", "NVIDIA Nemotron 3.5"),
    # GLM
    (r"(\bglm\b|जीएलएम)", "opencode_glm", "GLM 5.3 Flash"),
    # OpenRouter
    (r"(open\s*router|ओपन\s*राउटर)", "openrouter", "OpenRouter"),
    # Sarvam AI
    (r"(sarvam|सर्वम|सरवम)", "sarvam", "Sarvam AI"),
    # Ollama / Local (bare "local" only when clearly about the model/engine)
    (r"(ollama|ओलामा|local\s+(?:model|ai|brain|llm|engine))", "local_fast", "Ollama Local"),
]

# Question markers: a conceptual question about a model must never trigger a switch.
_QUESTION_MARKERS = [
    "kya hota", "kya hai", "क्या होता", "क्या है", "matlab", "meaning",
    "what is", "difference", "antar", "explain", "samjhao", "समझाओ",
]

CONFIRM_CURRENT_PATTERNS = [
    r"यही\s*(ठीक|रहने\s*दो|चलेगा|सही)",
    r"इसी\s*(पर|मॉडल|पे)",
    r"\byahi\s*(theek|sahi|rehne\s*do|chalega)\b",
    r"\bisi\s*(par|pe|model)\b",
    r"\b(?:ec|e\.c\.|isi|ispe|iss)\s*model\b",
    r"\b(theek\s*hai|thik\s*hai|sahi\s*hai|chalega)\b",
    r"\b(?:continue|proceed)\s*(?:karo|kar\s*do|kro|karna)\b",
]

# Words that indicate the user actually wants a task done — a sentence mixing a
# confirmation phrase with a task must go to the AI instead of being swallowed.
_TASK_ACTION_WORDS = [
    "kholo", "खोलो", "chalao", "चलाओ", "banao", "बनाओ", "band", "बंद",
    "play", "open", "run", "likho", "लिखो", "search", "dhundo", "ढूंढो",
    "dikhao", "दिखाओ", "bhejo", "भेजो", "download", "delete", "set",
]


def get_friendly_model_name(model_key: str) -> str:
    """Return an Indian-friendly spoken name for an active AI model key."""
    return FRIENDLY_NAMES.get(model_key, model_key)


def detect_model_choice(text: str) -> Optional[Tuple[str, str]]:
    """
    Check if user's spoken words indicate a request to connect to a specific model.
    Returns (model_key, friendly_name) or None.
    """
    if not text:
        return None
    text_lower = text.lower()
    if any(m in text_lower for m in _QUESTION_MARKERS):
        return None
    for pattern, key, name in MODEL_PATTERNS:
        if re.search(pattern, text_lower):
            return key, name
    return None


def is_confirm_current(text: str) -> bool:
    """Check if the user wants to stay on the current active model."""
    if not text:
        return False
    text_lower = text.lower().strip()
    # A long sentence or one containing a real task action is NOT a confirmation.
    if len(text_lower.split()) > 6:
        return False
    if any(w in text_lower for w in _TASK_ACTION_WORDS):
        return False
    return any(re.search(p, text_lower) for p in CONFIRM_CURRENT_PATTERNS)


def format_model_greeting(active_model: str) -> str:
    """
    Crisp spoken acknowledgement when Hariom calls Victoria.
    No fluff, no questionnaire on every wake word.
    """
    return "जी हरिओम!"


def format_model_switched(display_name: str) -> str:
    """
    Spoken confirmation when the voice connection switches to chosen model.
    """
    return f"जी हरिओम, {display_name} कनेक्ट हो गया।"


def format_model_retained(display_name: str) -> str:
    """
    Spoken confirmation when retaining current model.
    """
    return f"जी हरिओम, {display_name} एक्टिव है।"


def extract_task_after_model(text: str) -> Optional[str]:
    """
    If the user combined model switching with a task in the same sentence
    (e.g., 'DeepSeek se connect karo aur terminal open karo'),
    extracts the remaining task ('terminal open karo') to execute immediately.
    """
    if not text:
        return None
    p = r"(?:connect|switch|activate|chalao|चलाओ|karo|करो|lagao|लगाओ|jodo|जोड़ो|badlo|बदलो)\s+(?:karke|kar ke|aur|and|fir|to|तथा|फिर|और)\s+(.+)"
    m = re.search(p, text, flags=re.IGNORECASE)
    if m and len(m.group(1).strip()) > 2:
        return m.group(1).strip()
    return None


VOICE_PATTERNS = [
    (r"(simran|सिमरन|सर्वम\s*आवाज़|sarvam\s*voice)", "simran", "सिमरन (सर्वम AI प्राकृतिक हिंदी)"),
    (r"(swara|स्वरा|पहली\s*आवाज़)", "swara", "स्वरा (भारतीय मधुर हिंदी)"),
    (r"(ava|एवा|ईवा|jarvis|मॉडर्न)", "ava", "एवा (जार्विस स्टाइल मॉडर्न AI)"),
    (r"(emma|एम्मा|एमा|सॉफ्ट)", "emma", "एम्मा (सॉफ्ट व स्पष्ट AI)"),
    (r"(seraphina|सेराफिना|रॉयल)", "seraphina", "सेराफ़िना (रॉयल AI)"),
    (r"(change\s*voice|voice\s*badlo|आवाज़\s*बदलो|दूसरी\s*आवाज़|अगली\s*आवाज़|different\s*voice|next\s*voice|voice\s*change)", "cycle", "अगली आवाज़"),
]


def detect_voice_choice(text: str) -> Optional[Tuple[str, str]]:
    """
    Check if user's spoken words indicate a request to switch Victoria's speaking voice.
    """
    if not text:
        return None
    text_lower = text.lower()
    for pattern, key, name in VOICE_PATTERNS:
        if re.search(pattern, text_lower):
            return key, name
    return None
