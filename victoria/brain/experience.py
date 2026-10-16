"""
Victoria - Task Experience & Self-Evolution Engine (कार्य अनुभव एवं आत्म-विकास इंजन)
Learns from every executed task, user corrections, feedback, and system habits.
Ensures Victoria continuously improves ("एक बार काम करने के बाद और बेहतर होती रहे").
"""

import json
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console

from victoria.config import PROJECT_ROOT

console = Console()

DB_DIR = PROJECT_ROOT / "data" / "memory"
DB_PATH = DB_DIR / "victoria.db"


class ExperienceEngine:
    """
    Self-Evolving Experiential Learning Engine.
    
    Responsibilities:
      1. Task Recipe Synthesis: Remembers multi-tool sequences that succeeded so future
         similar tasks are executed faster and more reliably.
      2. Correction & Rule Learning: Automatically extracts rules when the owner corrects
         behavior (e.g. 'next time do X', 'don't use Y', 'when I say Z, do W').
      3. Experiential Prompt Injection: Feeds past successes and guardrails into the
         AI brain before execution to prevent repeating past mistakes.
      4. Assistant Evolution Tracking: Measures assistant experience level, success rates,
         and learned skills over time.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get SQLite connection with Row factory and WAL mode."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_database(self):
        """Create task_recipes and learned_rules tables."""
        with self._get_connection() as conn:
            # 1. Optimal Task Recipes
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_recipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    intent_summary TEXT NOT NULL,
                    keywords TEXT NOT NULL,
                    tool_sequence TEXT NOT NULL,
                    success_count INTEGER NOT NULL DEFAULT 1,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    last_used REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    notes TEXT DEFAULT ''
                );
            """)

            # 2. Learned Rules and Corrections
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learned_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trigger_keywords TEXT NOT NULL,
                    rule_type TEXT NOT NULL DEFAULT 'correction',
                    rule_instruction TEXT NOT NULL,
                    learned_from TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    times_applied INTEGER NOT NULL DEFAULT 0
                );
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_recipe_keywords ON task_recipes(keywords);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rules_triggers ON learned_rules(trigger_keywords);")
            conn.commit()

        # Seed foundational learned rules if empty
        self._seed_initial_rules_if_empty()

    def _seed_initial_rules_if_empty(self):
        """Seed foundational rules on first run."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM learned_rules;")
            if cur.fetchone()[0] == 0:
                seeds = [
                    (
                        "autonomy execution permission",
                        "guardrail",
                        "मालिक के आदेश पर बिना किसी हिचकिचाहट या बार-बार अनुमति मांगे सीधे कार्य पूरा करें (Autonomous Execution)",
                        "प्रारंभिक निर्देश: परिणाम सबसे पहले",
                    ),
                    (
                        "language hindi voice",
                        "preference",
                        "हमेशा स्वाभाविक, आत्मीय और मधुर हिंदी/हिंग्लिश में मालिक से दो-तरफा बातचीत रखें",
                        "प्रारंभिक निर्देश: स्वाभाविक हिंदी",
                    ),
                    (
                        "screenshot capture screen",
                        "shortcut",
                        "स्क्रीनशॉट लेते समय तुरंत take_screenshot टूल चलाएं और मालिक को पाथ बताएं",
                        "प्रारंभिक वर्कफ़्लो",
                    ),
                    (
                        "system status battery cpu ram",
                        "shortcut",
                        "सिस्टम स्थिति पूछते ही get_system_info टूल चलाकर सीपीयू, रैम, डिस्क और बैटरी का संक्षेप दें",
                        "प्रारंभिक वर्कफ़्लो",
                    ),
                ]
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.executemany("""
                    INSERT INTO learned_rules (trigger_keywords, rule_type, rule_instruction, learned_from, created_at, times_applied)
                    VALUES (?, ?, ?, ?, ?, 1);
                """, [(s[0], s[1], s[2], s[3], now_str) for s in seeds])
                conn.commit()

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract normalized words from text (Hindi and English)."""
        words = re.findall(r"[\w]+", text.lower())
        # Filter common filler words
        stop_words = {
            "hai", "ho", "ka", "ki", "ke", "ko", "se", "me", "mein", "par", "ko",
            "karo", "kare", "karna", "the", "a", "an", "is", "are", "to", "for", "in"
        }
        return {w for w in words if len(w) > 2 and w not in stop_words}

    def learn_from_task(
        self,
        user_text: str,
        tools_called: list[dict],
        assistant_text: str,
    ):
        """
        Reflect on completed interaction and extract learned lessons, task recipes,
        and user corrections.
        """
        if not user_text or len(user_text.strip()) < 3:
            return

        user_lower = user_text.lower().strip()
        now_ts = time.time()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        keywords_set = self._extract_keywords(user_text)
        keywords_str = " ".join(keywords_set)

        # ---------------------------------------------------------
        # 1. Detect User Corrections & Rules ("गलती सुधार एवं नियम")
        # ---------------------------------------------------------
        correction_patterns = [
            (r"(?:agli\s+baar|next\s+time)\s+(?:se\s+)?(.+)", "correction"),
            (r"अगली\s+बार\s+(?:से\s+)?(.+)", "correction"),
            (r"(?:aisa|ye)\s+mat\s+karn?a[,\s]+(.+)", "correction"),
            (r"ऐसा\s+मत\s+करना[,\s]+(.+)", "correction"),
            (r"(?:jab\s+bhi|when\s+i\s+say)\s+(.+?)\s+(?:tab|to)\s+(.+)", "shortcut"),
            (r"जब\s+भी\s+(.+?)\s+(?:तब|तो)\s+(.+)", "shortcut"),
            (r"hamesha\s+(.+?)\s+(?:karna|use\s+karna)", "preference"),
            (r"हमेशा\s+(.+?)\s+(?:करना|इस्तेमाल\s+करना)", "preference"),
            (r"ye\s+galat\s+hai[,\s]+(.+)", "correction"),
            (r"यह\s+गलत\s+है[,\s]+(.+)", "correction"),
            (r"remember[,\s:]+(.+)", "preference"),
            (r"याद\s+रखना[,\s:]+(.+)", "preference"),
        ]

        for pattern, r_type in correction_patterns:
            m = re.search(pattern, user_lower)
            if m:
                if len(m.groups()) == 2:
                    trigger = m.group(1).strip()
                    instruction = f"जब '{trigger}' कहा जाए तो: {m.group(2).strip()}"
                else:
                    trigger = " ".join(list(keywords_set)[:4])
                    instruction = m.group(1).strip()

                if len(instruction) > 4:
                    self.add_rule(
                        trigger=trigger,
                        rule_instruction=instruction,
                        rule_type=r_type,
                        learned_from=user_text[:120],
                    )
                    console.print(f"[green]🧠 Victoria ने नया नियम सीखा: '{instruction}'[/green]")

        # ---------------------------------------------------------
        # 2. Synthesize or Update Task Recipe ("सफल वर्कफ़्लो रेसिपी")
        # ---------------------------------------------------------
        if tools_called:
            # Clean list of tool names and key arguments
            simplified_tools = [
                {"tool": t.get("name"), "args": t.get("arguments", {})}
                for t in tools_called
                if t.get("name") and t.get("name") != "switch_ai_model"
            ]

            if simplified_tools:
                intent_summary = user_text[:80].strip()
                tools_json = json.dumps(simplified_tools, ensure_ascii=False)

                with self._get_connection() as conn:
                    # Check if a matching recipe already exists for these keywords
                    cur = conn.execute("SELECT id, keywords, success_count FROM task_recipes;")
                    rows = cur.fetchall()

                    matched_id = None
                    for row in rows:
                        row_keywords = set(row["keywords"].split())
                        # Calculate keyword overlap
                        if row_keywords and keywords_set:
                            overlap = len(row_keywords.intersection(keywords_set))
                            similarity = overlap / max(len(row_keywords), len(keywords_set))
                            if similarity >= 0.5:
                                matched_id = row["id"]
                                break

                    if matched_id:
                        # Reinforce existing recipe
                        conn.execute("""
                            UPDATE task_recipes
                            SET success_count = success_count + 1,
                                last_used = ?,
                                tool_sequence = ?
                            WHERE id = ?;
                        """, (now_ts, tools_json, matched_id))
                        console.print(f"[green]📈 Task Recipe reinforced for '{intent_summary}' (ID: {matched_id})[/green]")
                    else:
                        # Insert fresh recipe
                        conn.execute("""
                            INSERT INTO task_recipes (
                                intent_summary, keywords, tool_sequence, success_count,
                                failure_count, last_used, created_at, notes
                            ) VALUES (?, ?, ?, 1, 0, ?, ?, '');
                        """, (intent_summary, keywords_str, tools_json, now_ts, now_str))
                        console.print(f"[green]✨ New Task Recipe mastered: '{intent_summary}'[/green]")

                    conn.commit()

    def add_rule(
        self,
        trigger: str,
        rule_instruction: str,
        rule_type: str = "correction",
        learned_from: str = "Owner direct input",
    ):
        """Add a learned rule or correction directly."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO learned_rules (
                    trigger_keywords, rule_type, rule_instruction,
                    learned_from, created_at, times_applied
                ) VALUES (?, ?, ?, ?, ?, 1);
            """, (trigger, rule_type, rule_instruction, learned_from, now_str))
            conn.commit()

    def get_relevant_experience(self, user_text: str) -> Optional[str]:
        """
        Recall relevant past task recipes and learned rules for the current user text.
        Injected into the system prompt so Victoria executes with past lessons in mind.
        """
        keywords_set = self._extract_keywords(user_text)
        if not keywords_set:
            return None

        matched_rules = []
        matched_recipes = []

        with self._get_connection() as conn:
            # 1. Match learned rules
            cur_rules = conn.execute("SELECT id, trigger_keywords, rule_type, rule_instruction FROM learned_rules;")
            for r in cur_rules.fetchall():
                trigger_words = set(re.findall(r"[\w]+", r["trigger_keywords"].lower()))
                if trigger_words.intersection(keywords_set):
                    matched_rules.append(r["rule_instruction"])
                    # Increment times applied
                    conn.execute("UPDATE learned_rules SET times_applied = times_applied + 1 WHERE id = ?;", (r["id"],))

            # 2. Match task recipes
            cur_recipes = conn.execute("""
                SELECT id, intent_summary, keywords, tool_sequence, success_count
                FROM task_recipes ORDER BY success_count DESC;
            """)
            for rc in cur_recipes.fetchall():
                rc_keywords = set(rc["keywords"].split())
                if rc_keywords and keywords_set:
                    overlap = len(rc_keywords.intersection(keywords_set))
                    if overlap >= 1 and (overlap / len(keywords_set) >= 0.3 or overlap >= 2):
                        try:
                            tools_parsed = json.loads(rc["tool_sequence"])
                            tool_names = [t.get("tool") for t in tools_parsed if t.get("tool")]
                            matched_recipes.append(f"• कार्य: '{rc['intent_summary']}' -> अनुशंसित टूल्स: {', '.join(tool_names)} (सफलता: {rc['success_count']} बार)")
                        except Exception:
                            pass

            conn.commit()

        if not matched_rules and not matched_recipes:
            return None

        # Build clean prompt injection
        lines = [
            "=== 🧠 पूर्व अनुभव एवं सीखी गई बातें (PAST EXPERIENCES & LEARNED WORKFLOWS) ===",
            "मालिक के साथ पिछले अनुभवों से विक्टोरिया ने ये नियम और वर्कफ़्लो सीखे हैं:",
        ]

        if matched_rules:
            lines.append("【सीखे गए नियम व सुधार】:")
            for rule in matched_rules[:4]:
                lines.append(f"  - {rule}")

        if matched_recipes:
            lines.append("【सिद्ध सफल वर्कफ़्लो (Optimal Proven Recipes)】:")
            for recipe in matched_recipes[:3]:
                lines.append(f"  {recipe}")

        lines.append("नियम: पिछली गलतियों को कभी न दोहराएं और इन सीखों का उपयोग करके कार्य को और भी बेहतर ढंग से पूरा करें।")
        lines.append("=============================================================================")

        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """Get learning statistics, IQ evolution level, and recent lessons."""
        with self._get_connection() as conn:
            cur_recipes = conn.execute("SELECT COUNT(*) FROM task_recipes;")
            total_recipes = cur_recipes.fetchone()[0]

            cur_rules = conn.execute("SELECT COUNT(*) FROM learned_rules;")
            total_rules = cur_rules.fetchone()[0]

            # Fetch recent rules
            cur_recent_rules = conn.execute("""
                SELECT id, trigger_keywords, rule_type, rule_instruction, created_at, times_applied
                FROM learned_rules ORDER BY id DESC LIMIT 10;
            """)
            rules_list = [dict(r) for r in cur_recent_rules.fetchall()]

            # Fetch top recipes
            cur_top_recipes = conn.execute("""
                SELECT id, intent_summary, tool_sequence, success_count, created_at
                FROM task_recipes ORDER BY success_count DESC LIMIT 10;
            """)
            recipes_list = []
            for r in cur_top_recipes.fetchall():
                d = dict(r)
                try:
                    d["tools"] = json.loads(d["tool_sequence"])
                except Exception:
                    d["tools"] = []
                recipes_list.append(d)

        # Calculate Assistant Evolution Score / Level
        evolution_score = (total_recipes * 15) + (total_rules * 25)
        level = max(1, 1 + (evolution_score // 100))

        return {
            "total_recipes": total_recipes,
            "total_rules": total_rules,
            "evolution_score": evolution_score,
            "evolution_level": level,
            "level_title": self._get_level_title(level),
            "recent_rules": rules_list,
            "top_recipes": recipes_list,
        }

    def _get_level_title(self, level: int) -> str:
        """Get human-readable evolution rank."""
        titles = {
            1: "नवागंतुक (Apprentice Assistant)",
            2: "सतर्क शिक्षार्थी (Attentive Learner)",
            3: "कुशल सहयोगी (Skilled Digital Twin)",
            4: "अग्रिम हमशक्ल (Advanced Alter Ego)",
            5: "पूर्ण स्वायत्त साथी (Autonomous Master Partner)",
        }
        return titles.get(level, "परम डिजिटल हमशक्ल (Supreme Digital Twin)")


# Global Singleton Instance
_experience_engine: Optional[ExperienceEngine] = None


def get_experience_engine() -> ExperienceEngine:
    """Get or initialize global ExperienceEngine singleton."""
    global _experience_engine
    if _experience_engine is None:
        _experience_engine = ExperienceEngine()
    return _experience_engine
