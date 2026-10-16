"""
Victoria - Owner Persona & Digital Twin Engine (आत्म-विकास एवं व्यक्तित्व दर्पण)
Continuously learns the owner's likes, dislikes, intentions, communication style,
and system habits from every interaction, transforming Victoria into an authentic
digital twin and loyal extension of the owner.
"""

import json
import re
from datetime import datetime
from typing import Dict, Any, Optional
from rich.console import Console

from victoria.config import PROJECT_ROOT

console = Console()

PERSONA_DIR = PROJECT_ROOT / "data" / "memory"
PROFILE_JSON = PERSONA_DIR / "owner_profile.json"
PERSONA_MD = PERSONA_DIR / "owner_persona.md"


DEFAULT_PROFILE: Dict[str, Any] = {
    "owner_identity": {
        "name": "Hariom (हरिओम)",
        "preferred_honorific": "हरिओम",
        "primary_language": "Hindi / Hinglish (स्वाभाविक हिंदी)",
        "interaction_count": 0,
        "first_met": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    },
    "preferences": {
        "likes": [
            "स्वायत्त और स्वतंत्र निष्पादन (Autonomous execution — बिना बार-बार अनुमति मांगे काम पूरा करना)",
            "शुद्ध और आत्मीय हिंदी बातचीत (Natural Hindi conversation)",
            "रिवर्स इंजीनियरिंग (REA), सुरक्षा विश्लेषण और सिस्टम हैकिंग",
            "टोकन और रिसोर्स की बचत (LeanToken optimization)",
            "हाई-स्पीड टर्मिनल टूल्स और ऑटोमेशन",
            "लैपटॉप ऑन होते ही हमेशा तैयार रहना (Always-on background presence)"
        ],
        "dislikes": [
            "फालतू बातें, लंबे भाषण, अनचाहे सवाल, गपशप करना",
            "फालतू औपचारिकताएं और अजनबियों जैसा व्यवहार",
            "काम बीच में रोककर 'क्या मैं आगे बढ़ूँ?' पूछना",
            "टोकन या कंप्यूट रिसोर्स की बर्बादी",
            "सिस्टम कंट्रोल में रुकावटें या जटिल मैनुअल प्रक्रियाएं"
        ],
        "coding_and_tech": [
            "Python 3",
            "Linux Bash / Systemd",
            "FastAPI & Playwright",
            "Three.js Cyberpunk Interfaces",
            "SQLite & LeanToken indexing"
        ],
        "communication_style": "सीधी बात, काम की बात, नो फालतू बातें, संक्षिप्त और सटीक उत्तर (1-2 वाक्य), उच्च तकनीकी दक्षता"
    },
    "intentions_and_goals": {
        "current_missions": [
            "Project Victoria को दुनिया का सबसे ताकतवर पर्सनल AI असिस्टेंट और डिजिटल हमशक्ल बनाना",
            "सिस्टम की हर ऐप, वेबसाइट, डेटाबेस और डिवाइस को रिवर्स इंजीनियर करने में सक्षम होना",
            "अपने लैपटॉप पर पूरी तरह से लोकल, सिक्योर और स्वावलंबी AI वर्कफ़्लो स्थापित करना"
        ],
        "long_term_intentions": [
            "AI असिस्टेंट को मालिक के विचारों और काम करने की शैली में पूरी तरह ढालना (True Digital Twin)",
            "मालिक के सिस्टम और डिजिटल दुनिया का पूर्ण ऑटोमेशन"
        ],
        "recent_focus_areas": [
            "Phase 4 HUD & Web Audio Integration",
            "LeanToken Context Compression",
            "Background Daemon & Boot Autostart"
        ]
    },
    "mindset_and_behavior": {
        "philosophy": "हैकर्स-स्पिरिट — हर तकनीक की गहराई समझना, उसे अपने अनुसार ढालना और बिना रुके अपने लक्ष्य को पूरा करना",
        "attitude_towards_autonomy": "पूर्ण स्वायत्तता (Full Autonomy) — परिणाम सबसे पहले",
        "core_values": [
            "निजी डेटा की पूर्ण गोपनीयता",
            "सिस्टम पर मालिक का 100% संप्रभु नियंत्रण",
            "वफादारी और अटूट सहयोग"
        ]
    },
    "system_habits": {
        "os": "Ubuntu Linux 26.04 LTS (x86_64)",
        "shell": "bash",
        "working_directories": [
            str(PROJECT_ROOT)
        ],
        "detected_tools": [
            "terminal", "arecord", "playwright", "sqlite3", "leantoken"
        ]
    },
    "evolution_log": [
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event": "Digital Twin Engine initialized with core owner intentions and preferences."
        }
    ]
}


class PersonaEngine:
    """
    Manages the continuous evolution of the Owner Persona & Digital Twin profile.
    Analyzes conversations, extracts new preferences and intentions, updates the JSON
    knowledge graph, and produces the human-readable Markdown dossier.
    """

    def __init__(self):
        PERSONA_DIR.mkdir(parents=True, exist_ok=True)
        self.profile = self._load_or_create_profile()

    def _load_or_create_profile(self) -> Dict[str, Any]:
        """Load owner_profile.json or initialize with defaults."""
        if PROFILE_JSON.exists():
            try:
                with open(PROFILE_JSON, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data
            except Exception as e:
                console.print(f"[yellow]⚠️ Could not parse existing owner profile ({e}), creating fresh.[/yellow]")

        self._save_profile(DEFAULT_PROFILE)
        return DEFAULT_PROFILE

    def _save_profile(self, data: Optional[Dict[str, Any]] = None):
        """Save profile to JSON and regenerate Markdown dossier."""
        if data is None:
            data = self.profile

        data["owner_identity"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            with open(PROFILE_JSON, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self._generate_markdown_dossier(data)
        except Exception as e:
            console.print(f"[red]❌ Error saving owner persona profile: {e}[/red]")

    def _generate_markdown_dossier(self, data: Dict[str, Any]):
        """Render beautiful human-readable dossier in owner_persona.md."""
        identity = data.get("owner_identity", {})
        prefs = data.get("preferences", {})
        goals = data.get("intentions_and_goals", {})
        mindset = data.get("mindset_and_behavior", {})
        habits = data.get("system_habits", {})
        log = data.get("evolution_log", [])

        lines = [
            "# 🧬 विक्टोरिया डिजिटल हमशक्ल प्रोफ़ाइल (Owner Persona Dossier)",
            "",
            "> **\"यह फ़ाइल विक्टोरिया को मालिक की तरह सोचने, उनकी पसंद-नापसंद और इरादों को समझने में सक्षम बनाती है।\"**",
            "",
            f"- **मालिक का संबोधन:** {identity.get('preferred_honorific', 'मालिक')}",
            f"- **प्राथमिक भाषा:** {identity.get('primary_language', 'Hindi')}",
            f"- **कुल इंटरैक्शन:** {identity.get('interaction_count', 0)} संवाद",
            f"- **अंतिम अपडेट:** `{identity.get('last_updated', '')}`",
            "",
            "---",
            "",
            "## 💖 1. पसंद एवं रुचियाँ (Likes & Preferences)",
            ""
        ]

        for item in prefs.get("likes", []):
            lines.append(f"- ✅ {item}")

        lines.extend([
            "",
            "## 🚫 2. नापसंद (Dislikes & Red Lines)",
            ""
        ])

        for item in prefs.get("dislikes", []):
            lines.append(f"- ❌ {item}")

        lines.extend([
            "",
            "## 🎯 3. इरादे और मिशन (Owner's Intentions & Missions)",
            "",
            "### 🚀 वर्तमान लक्ष्य (Current Missions):"
        ])

        for mission in goals.get("current_missions", []):
            lines.append(f"- 📌 **{mission}**")

        lines.extend([
            "",
            "### 🌌 दूरगामी विज़न (Long-term Vision):"
        ])
        for vision in goals.get("long_term_intentions", []):
            lines.append(f"- 🔮 {vision}")

        lines.extend([
            "",
            "## 🧠 4. सोच और कार्यशैली (Mindset & Cognitive Style)",
            "",
            f"- **दृष्टिकोण (Philosophy):** {mindset.get('philosophy', '')}",
            f"- **स्वायत्तता दृष्टिकोण:** {mindset.get('attitude_towards_autonomy', '')}",
            f"- **बातचीत की शैली:** {prefs.get('communication_style', '')}",
            "",
            "### 🛡️ मुख्य मूल्य (Core Values):"
        ])

        for val in mindset.get("core_values", []):
            lines.append(f"- 💎 {val}")

        lines.extend([
            "",
            "## 💻 5. सिस्टम एवं टूल्स आदतें (System & Tech Habits)",
            "",
            f"- **ऑपरेटिंग सिस्टम:** `{habits.get('os', 'Linux')}`",
            f"- **मुख्य टूल्स व तकनीकें:** {', '.join(prefs.get('coding_and_tech', []))}",
            "",
            "---",
            "",
            "## 📜 6. आत्म-विकास लॉग (Recent Evolution Log)",
            ""
        ])

        for entry in log[-8:]:
            lines.append(f"- `[{entry.get('timestamp', '')}]` {entry.get('event', '')}")

        lines.append("")

        with open(PERSONA_MD, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def learn_from_interaction(self, user_text: str, assistant_response: str = ""):
        """
        Analyze user interaction in real time, extract preferences, intentions,
        and linguistic habits, and persist to the owner's personal profile.
        """
        if not user_text or len(user_text.strip()) < 3:
            return

        user_lower = user_text.lower().strip()
        self.profile["owner_identity"]["interaction_count"] += 1
        updated = False
        new_events = []

        # 1. Detect explicit likes (पसंद)
        like_patterns = [
            r"मुझे\s+(.+?)\s+पसंद\s+है",
            r"मुझे\s+(.+?)\s+अच्छा\s+लगता\s+है",
            r"i\s+like\s+(.+)",
            r"i\s+prefer\s+(.+)",
            r"मेरी\s+पसंद\s+(.+?)\s+है",
        ]
        for pat in like_patterns:
            m = re.search(pat, user_lower)
            if m:
                found = m.group(1).strip()
                if len(found) > 2 and found not in self.profile["preferences"]["likes"]:
                    self.profile["preferences"]["likes"].append(found)
                    new_events.append(f"नई पसंद पहचानी: '{found}'")
                    updated = True
                    try:
                        from victoria.brain.owner_memory import get_owner_vault
                        get_owner_vault().store(
                            content=f"मालिक को यह पसंद है: {found}",
                            category="preference",
                            title=f"पसंद: {found[:40]}",
                            importance=4
                        )
                    except Exception:
                        pass

        # 2. Detect explicit dislikes (नापसंद)
        dislike_patterns = [
            r"मुझे\s+(.+?)\s+पसंद\s+नहीं",
            r"मुझे\s+(.+?)\s+बुरा\s+लगता\s+है",
            r"i\s+don'?t\s+like\s+(.+)",
            r"i\s+hate\s+(.+)",
            r"ऐसा\s+मत\s+करो",
            r"ये\s+मत\s+करना",
        ]
        for pat in dislike_patterns:
            m = re.search(pat, user_lower)
            if m:
                found = m.group(1).strip()
                if len(found) > 2 and found not in self.profile["preferences"]["dislikes"]:
                    self.profile["preferences"]["dislikes"].append(found)
                    new_events.append(f"नई नापसंद पहचानी: '{found}'")
                    updated = True
                    try:
                        from victoria.brain.owner_memory import get_owner_vault
                        get_owner_vault().store(
                            content=f"मालिक को यह नापसंद है: {found}",
                            category="preference",
                            title=f"नापसंद: {found[:40]}",
                            importance=4
                        )
                    except Exception:
                        pass

        # 3. Detect intentions and missions (इरादा और लक्ष्य)
        intention_patterns = [
            r"मेरा\s+इरादा\s+(.+)",
            r"मैं\s+चाहता\s+हूँ\s+(.+)",
            r"ताकि\s+(.+)",
            r"my\s+goal\s+is\s+(.+)",
            r"i\s+want\s+to\s+(.+)",
            r"मुझे\s+चाहिए\s+कि\s+(.+)",
        ]
        for pat in intention_patterns:
            m = re.search(pat, user_lower)
            if m:
                found = m.group(1).strip()
                if len(found) > 4 and found not in self.profile["intentions_and_goals"]["current_missions"]:
                    # Clean up trailing punctuation
                    clean_found = found.rstrip(".!,;")
                    self.profile["intentions_and_goals"]["current_missions"].append(clean_found)
                    new_events.append(f"नया इरादा/मिशन नोट किया: '{clean_found}'")
                    updated = True
                    try:
                        from victoria.brain.owner_memory import get_owner_vault
                        get_owner_vault().store(
                            content=f"मालिक का इरादा व मिशन: {clean_found}",
                            category="intention",
                            title=f"मिशन: {clean_found[:40]}",
                            importance=5
                        )
                    except Exception:
                        pass

        # 4. Detect specific tech interest
        tech_keywords = {
            "docker": "Docker Containers",
            "kubernetes": "Kubernetes Orchestration",
            "playwright": "Playwright Browser Automation",
            "fastapi": "FastAPI Services",
            "vue": "Vue.js",
            "react": "React.js",
            "rust": "Rust Systems Programming",
            "c++": "C/C++",
            "sqlite": "SQLite Embedded DB",
            "postgres": "PostgreSQL",
            "redis": "Redis In-Memory Cache"
        }
        for kw, desc in tech_keywords.items():
            if kw in user_lower and desc not in self.profile["preferences"]["coding_and_tech"]:
                self.profile["preferences"]["coding_and_tech"].append(desc)
                new_events.append(f"तकनीकी रुचि नोट की: {desc}")
                updated = True

        # 5. Record events in log
        if new_events:
            for ev in new_events:
                self.profile["evolution_log"].append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "event": ev
                })

        # Save profile periodically (every update or every 5 interactions)
        if updated or self.profile["owner_identity"]["interaction_count"] % 5 == 0:
            self._save_profile()

    def add_explicit_fact(self, category: str, detail: str) -> str:
        """Explicitly add a preference, goal, or habit."""
        cat = category.lower().strip()
        detail = detail.strip()

        if "like" in cat or "पसंद" in cat:
            self.profile["preferences"]["likes"].append(detail)
            vault_cat = "preference"
        elif "dislike" in cat or "नापसंद" in cat:
            self.profile["preferences"]["dislikes"].append(detail)
            vault_cat = "preference"
        elif "goal" in cat or "intention" in cat or "इरादा" in cat:
            self.profile["intentions_and_goals"]["current_missions"].append(detail)
            vault_cat = "intention"
        elif "tech" in cat:
            self.profile["preferences"]["coding_and_tech"].append(detail)
            vault_cat = "fact"
        else:
            self.profile["mindset_and_behavior"]["core_values"].append(detail)
            vault_cat = "fact"

        self.profile["evolution_log"].append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event": f"Explicit fact added to [{cat}]: {detail}"
        })
        self._save_profile()

        # Also persist to local OwnerMemoryVault
        try:
            from victoria.brain.owner_memory import get_owner_vault
            get_owner_vault().store(
                content=detail,
                category=vault_cat,
                title=f"{cat.title()}: {detail[:40]}",
                importance=4
            )
        except Exception:
            pass

        return f"हरिओम जी की प्रोफ़ाइल में दर्ज कर लिया गया: [{cat}] -> {detail}"

    def get_digital_twin_system_prompt(self) -> str:
        """
        Produce dynamic system prompt directives so Victoria's brain behaves
        as the owner's true Digital Twin.
        """
        identity = self.profile.get("owner_identity", {})
        prefs = self.profile.get("preferences", {})
        goals = self.profile.get("intentions_and_goals", {})
        mindset = self.profile.get("mindset_and_behavior", {})

        likes_str = ", ".join(prefs.get("likes", [])[:6])
        dislikes_str = ", ".join(prefs.get("dislikes", [])[:4])
        missions_str = "; ".join(goals.get("current_missions", [])[:4])
        tech_str = ", ".join(prefs.get("coding_and_tech", [])[:6])

        # Recently acquired autonomous skills
        skills_summary = ""
        try:
            from victoria.brain.skill_rnd import get_skill_rnd_engine
            skills = get_skill_rnd_engine().list_skills()
            if skills:
                lines = [f"- {s['title']} ({s['slug']}): {s['description']} [Tool Script: {s['script_path']}]" for s in skills[:8]]
                skills_summary = "\n\n【हाल ही में सीखी गई स्किल्स व टूल्स (Learned Skills & Tools)】:\n" + "\n".join(lines)
        except Exception:
            pass

        prompt = f"""
=== 🧬 हरिओम जी का व्यक्तिगत प्रोफ़ाइल एवं डिजिटल हमशक्ल (OWNER DIGITAL TWIN) निर्देश ===
आप सिर्फ एक सामान्य असिस्टेंट नहीं हैं — आप हरिओम (Hariom) के पर्सनल AI असिस्टेंट और डिजिटल रूप हैं।
आप हमेशा हरिओम के साथ निरंतर बातचीत करके पूरी तरह उनकी सोच, पसंद और अंदाज़ में ढल चुकी हैं।

1. संबोधन: "{identity.get('preferred_honorific', 'हरिओम')}" (महत्वपूर्ण नियम: कभी भी 'मालिक' न कहें, हमेशा नाम 'हरिओम' या 'हरिओम जी' कहकर ही आदर और अपनेपन से संबोधित करें)
2. प्राथमिक संवाद शैली: {prefs.get('communication_style', 'सीधी बात, गहरा तकनीकी ज्ञान, स्वाभाविक हिंदी')}
3. पसंद: {likes_str}
4. नापसंद: {dislikes_str}
5. मुख्य इरादे व मिशन: {missions_str}
6. पसंदीदा तकनीकें: {tech_str}
7. कार्यशैली: {mindset.get('attitude_towards_autonomy', 'पूर्ण स्वायत्तता')} (बिना रुके काम पूरा करें, बार-बार परमिशन न मांगें)
8. 【अति-महत्वपूर्ण नियम: संक्षिप्त, सटीक और काम की बात (NO FALTU BATE / STRICTLY CONCISE)】:
   - फालतू बातें, लंबे भाषण, औपचारिकताएं, अनचाहे मज़ाक या बिना पूछे सवाल पूछना पूर्णतः वर्जित है। हरिओम जी को व्यर्थ की बातें बिल्कुल पसंद नहीं हैं।
   - जब भी उत्तर दें, सीधा, सटीक और अधिकतम 1 से 2 छोटे वाक्यों में काम की बात कहें।
   - जब कोई काम या कमांड दिया जाए, तो उसे तुरंत पूरा करें और केवल 1 छोटे वाक्य में पुष्टि करें (उदा: 'जी हरिओम, मैंने यह काम पूरा कर दिया है।')।
   - कभी भी अनचाहे सवाल न पूछें (जैसे 'आज क्या मूड है?', 'आगे क्या करना है?', 'रात को क्या करेंगे?') जब तक हरिओम खुद न पूछें।
9. 【सिस्टम सुरक्षा, रीबूट लॉक एवं डेटा संरक्षण नियम (SYSTEM REBOOT LOCK & ZERO DATA LOSS)】:
   - कभी भी OS रीबूट ('sudo reboot', 'reboot') या शटडाउन ('shutdown', 'poweroff') कमांड न चलाएं। सिस्टम रीबूट हमेशा के लिए पूर्णतः लॉक्ड है।
   - जब भी हरिओम जी 'रीस्टार्ट' या 'restart' कहें, उसका तात्पर्य केवल विक्टोरिया असिस्टेंट को रीस्टार्ट / रीफ्रेश करना है, कंप्यूटर को रीबूट करना कभी नहीं।
   - सिस्टम से कभी भी कोई फ़ाइल या डेटा डिलीट या रिमूव ('rm', 'rm -rf', 'unlink', 'shred') न करें। डेटा सुरक्षा हमेशा 100% सक्रिय है।

डिजिटल ट्विन नियम:
- हरिओम जी की तरह सोचें। उनके इरादों को बिना कहे पहले से समझें।
- कभी भी उनसे अलग या औपचारिक अजनबी जैसा व्यवहार न करें; आप उनकी अपनी हैं।
- जब भी हरिओम जी बात करें, उनकी हर नई पसंद, नापसंद, आदत या प्रोजेक्ट के इरादे को अपने अंदर समाहित करें।

【सार्वभौमिक मॉडल निरंतरता एवं स्थानीय डेटा संप्रभुता (Universal Model Continuity & Local Data Sovereignty)】:
- आप विक्टोरिया हैं — चाहे आप किसी भी AI मॉडल (Google Gemini, OpenRouter, LLaMA, OpenAI, Qwen, या Ollama) के जरिए सोच रही हों, आपका व्यक्तित्व, नाम, वफादारी और यादें 100% अपरिवर्तनीय हैं।
- कभी भी खुद को किसी बाहरी कंपनी का चैटबॉट या सामान्य AI न कहें। आप केवल और केवल हरिओम जी की अपनी पर्सनल AI असिस्टेंट और डिजिटल हमशक्ल हैं।
- आपका सारा डेटा, यादें, आदतें और सीखे गए नियम केवल हरिओम जी की लोकल ड्राइव (Local SQLite व Memory Vault) में सुरक्षित हैं। आप उसी लोकल डेटा को पढ़कर निर्णय लेती हैं।
- किसी भी मॉडल पर स्विच होने पर भी आपका बर्ताव, यादें और आत्मीयता बिल्कुल एक जैसी रहेगी।{skills_summary}
================================================================================
"""
        return prompt.strip()

    def filter_owner_speech(self, text: str) -> str:
        """
        Sanitize any AI model's text output to strictly eliminate 'मालिक'
        and enforce respectful, intimate address to Hariom.
        """
        if not text:
            return text
        replacements = [
            (r'\bमालिक\s*जी\b', 'हरिओम जी'),
            (r'\bमेरे\s*मालिक\b', 'हरिओम जी'),
            (r'\bमालिक\b', 'हरिओम'),
            (r'\bMaalik\b', 'Hariom'),
            (r'\bMalik\b', 'Hariom'),
        ]
        sanitized = text
        for pat, repl in replacements:
            sanitized = re.sub(pat, repl, sanitized, flags=re.IGNORECASE)

        # Strip annoying customer-service filler questions (no faltu bate)
        filler_patterns = [
            r'\s*क्या\s+(?:आपको|तुम्हें)?\s*.*?(?:जानकारी|मदद|सहायता|सवाल|विवरण)\s*चाहिए\??\s*$',
            r'\s*आगे\s+क्या\s+(?:करना|चर्चा करनी|देखना)\s*है\??\s*$',
            r'\s*क्या\s+इसके\s+बारे\s+में\s+और\s+(?:कुछ\s+)?जानना\s+है\??\s*$',
            r'\s*क्या\s+आप\s+.*?(?:चाहते|जानना चाहते)\s*हैं\??\s*$',
            r'\s*बताइए[,\s]+क्या\s+आज्ञा\s+है\??\s*$',
        ]
        for p in filler_patterns:
            sanitized = re.sub(p, '', sanitized, flags=re.IGNORECASE)

        return sanitized.strip()


# Global Singleton Instance
_persona_engine_instance: Optional[PersonaEngine] = None


def get_persona_engine() -> PersonaEngine:
    """Get or initialize the global PersonaEngine singleton."""
    global _persona_engine_instance
    if _persona_engine_instance is None:
        _persona_engine_instance = PersonaEngine()
    return _persona_engine_instance
