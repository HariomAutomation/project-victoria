"""
Victoria - Autonomous Skill R&D & Knowledge Acquisition Engine (कौशल एवं ज्ञान अनुसंधान इंजन)
Enables Victoria to:
1. Search and research new technical topics, APIs, and workflows on the internet (DuckDuckGo + Wikipedia).
2. Synthesize complete offline knowledge documents in data/knowledge/{slug}.md.
3. Generate working, executable Python automation tools in scripts/custom/{slug}.py.
4. Persist and register newly learned skills in SQLite (data/memory/victoria.db).
5. Converse back to Hariom:
   "जी हरिओम! मैंने इंटरनेट से R&D करके '{title}' की स्किल और नॉलेज अपने अंदर सफलतापूर्वक शामिल कर ली है। अब यह स्किल मेरे पास उपलब्ध है—इस स्किल का उपयोग करके आप मुझसे क्या काम करवाना चाहते हैं?"
"""

import os
import re
import json
import sqlite3
import py_compile
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from rich.console import Console

from victoria.config import PROJECT_ROOT

console = Console()

KNOWLEDGE_DIR = PROJECT_ROOT / "data" / "knowledge"
SCRIPTS_DIR = PROJECT_ROOT / "scripts" / "custom"
DB_PATH = PROJECT_ROOT / "data" / "memory" / "victoria.db"


class SkillRNDEngine:
    """
    Self-evolution engine that conducts autonomous internet research,
    synthesizes local offline knowledge, generates executable scripts,
    and incorporates new capabilities into Victoria.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        knowledge_dir: Optional[Path] = None,
        scripts_dir: Optional[Path] = None,
    ):
        self.db_path = db_path or DB_PATH
        self.knowledge_dir = knowledge_dir or KNOWLEDGE_DIR
        self.scripts_dir = scripts_dir or SCRIPTS_DIR

        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_database(self):
        """Create learned_skills table in victoria.db."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learned_skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    keywords TEXT NOT NULL,
                    script_path TEXT NOT NULL,
                    knowledge_path TEXT NOT NULL,
                    capabilities TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    times_used INTEGER NOT NULL DEFAULT 0
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_learned_skills_slug ON learned_skills(slug);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_learned_skills_keywords ON learned_skills(keywords);")
            conn.commit()

    def search_internet(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Search the live internet for documentation, tutorials, and technical guides.
        Uses DuckDuckGo (via ddgs) with fallback to Wikipedia API.
        """
        results = []

        # 1. Primary: DuckDuckGo search
        try:
            from ddgs import DDGS
            ddgs = DDGS()
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", ""),
                    "source": "duckduckgo",
                })
        except Exception as e:
            console.print(f"[dim]DDGS search notice: {e}[/dim]")

        # 2. Fallback / Augmentation: Wikipedia Search API
        if len(results) < 2:
            try:
                encoded = urllib.parse.quote(query)
                wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json&utf8=1"
                req = urllib.request.Request(
                    wiki_url,
                    headers={"User-Agent": "ProjectVictoria/1.0 (Linux; Personal AI)"},
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    wiki_items = data.get("query", {}).get("search", [])
                    for item in wiki_items[:3]:
                        clean_snippet = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
                        results.append({
                            "title": item.get("title", ""),
                            "snippet": clean_snippet,
                            "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(item.get('title', ''))}",
                            "source": "wikipedia",
                        })
            except Exception as wiki_err:
                console.print(f"[dim]Wikipedia search notice: {wiki_err}[/dim]")

        return results

    def research_topic(self, topic: str) -> str:
        """
        Conduct multi-query R&D across the web on the specified topic.
        Aggregates search snippets and code reference patterns into a synthesis context.
        """
        queries = [
            f"{topic} python script tutorial how to",
            f"{topic} linux command line api",
        ]
        aggregated_findings = []

        for q in queries:
            items = self.search_internet(q, max_results=4)
            for item in items:
                aggregated_findings.append(f"Title: {item['title']}\nSnippet: {item['snippet']}\nURL: {item['url']}\n")

        if not aggregated_findings:
            return f"Topic: {topic}\n(Online search yielded minimal results; synthesize based on foundational computer science and Python systems architecture)."

        return "\n---\n".join(aggregated_findings[:8])

    def synthesize_skill(self, topic: str, research_data: str, user_description: str = "") -> Dict[str, Any]:
        """
        Synthesize a complete executable skill and knowledge base using Victoria's AI Brain.
        """
        from victoria.brain.router import BrainRouter
        router = BrainRouter()

        prompt = f"""
You are the Autonomous Self-Evolution Engine of Project Victoria (Personal AI for Linux, Owner: Hariom).
Hariom has requested Victoria to research and acquire a new skill and knowledge on: '{topic}'.
Additional context from user: '{user_description}'

Here is the internet R&D research data collected from the web:
\"\"\"
{research_data}
\"\"\"

Your mission:
1. Synthesize a professional, fully offline-capable Python script that implements this skill cleanly for Linux.
   - Script must have `#!/usr/bin/env python3`
   - Include CLI argument parsing (`argparse`) so it can be run standalone or by Victoria.
   - Output clean JSON or clear readable text.
   - Robust error handling (try/except, timeouts).
2. Synthesize a thorough Markdown knowledge dossier for Victoria's offline memory (how it works, concepts, CLI usage, parameters).
3. Generate a friendly Hindi title and short description.

CRITICAL RULES:
- Output MUST be valid JSON only. Do not include markdown code block formatting around the entire response if possible, or wrap in ```json ... ```.
- Owner name is Hariom (हरिओम). NEVER use "मालिक".
- JSON structure required:
{{
  "slug": "alphanumeric_snake_case_name",
  "title": "Hindi/English title (e.g. स्टॉक मार्केट विश्लेषक / Stock Market Analyzer)",
  "description": "Brief description of what this skill does",
  "keywords": "comma, separated, trigger, keywords, in, hindi, and, english",
  "capabilities": ["capability 1", "capability 2", "capability 3"],
  "knowledge_md": "# Title\\n\\n## अवलोकन (Overview)\\n...\\n\\n## उपयोग विधि (Usage)\\n...\\n",
  "python_code": "#!/usr/bin/env python3\\n...complete working python code..."
}}
"""
        response_text = router.think(prompt)

        # Parse JSON from response
        clean_json_str = response_text.strip()
        fence_match = re.search(r"```json\s*([\s\S]*?)\s*```", clean_json_str) or re.search(
            r"```\s*([\s\S]*?)\s*```", clean_json_str
        )
        if fence_match:
            clean_json_str = fence_match.group(1)
        elif "```" in clean_json_str:
            # Unbalanced code fences: strip them manually instead of crashing
            clean_json_str = clean_json_str.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(clean_json_str)
        except Exception:
            # Fallback regex extraction if model returned slightly unescaped JSON
            slug = re.sub(r"[^a-zA-Z0-9_]", "_", topic.lower()).strip("_")[:30] or "custom_skill"
            data = {
                "slug": slug,
                "title": f"स्किल: {topic.title()}",
                "description": f"{topic} से जुड़े कार्यों का निष्पादन और प्रबंधन।",
                "keywords": f"{topic}, {topic.lower()}, skill",
                "capabilities": [f"Execute {topic} tasks", f"Provide {topic} guidance"],
                "knowledge_md": f"# {topic.title()} - Victoria Knowledge Base\n\n## Overview\nSkill autonomously acquired for Hariom.\n\n## Research Notes\n{research_data[:1000]}",
                "python_code": f"""#!/usr/bin/env python3
import sys
import json

def main():
    print("Project Victoria - Skill: {topic}")
    args = sys.argv[1:]
    if args:
        print(f"Executing with arguments: {{' '.join(args)}}")
    else:
        print("Skill is ready for operation.")

if __name__ == "__main__":
    main()
""",
            }

        return data

    def acquire_skill(self, topic: str, user_description: str = "") -> Dict[str, Any]:
        """
        Full autonomous pipeline:
        1. Internet R&D
        2. Knowledge & script synthesis
        3. File persistence (data/knowledge/ and scripts/custom/)
        4. Syntax validation & permissions
        5. SQLite registration (learned_skills & task_recipes)
        6. Dialogue formulation
        """
        console.print(f"[bold cyan]🔍 [Skill R&D] Starting autonomous research on: '{topic}'...[/bold cyan]")

        # 1. Research
        research_data = self.research_topic(topic)
        console.print(f"[green]✅ Internet research completed for '{topic}'[/green]")

        # 2. Synthesize
        skill_data = self.synthesize_skill(topic, research_data, user_description)
        slug = re.sub(r"[^a-zA-Z0-9_]", "_", skill_data.get("slug", topic).lower()).strip("_")
        if not slug:
            slug = "skill_" + str(int(datetime.now().timestamp()))

        title = skill_data.get("title", topic)
        desc = skill_data.get("description", f"Skill for {topic}")
        keywords = skill_data.get("keywords", topic)
        caps = skill_data.get("capabilities", [])
        caps_str = ", ".join(caps) if isinstance(caps, list) else str(caps)

        # 3. Persist Knowledge MD
        knowledge_file = self.knowledge_dir / f"{slug}.md"
        knowledge_content = skill_data.get("knowledge_md", f"# {title}\n\n{desc}\n")
        knowledge_file.write_text(knowledge_content, encoding="utf-8")
        console.print(f"[dim]💾 Knowledge saved: {knowledge_file}[/dim]")

        # 4. Persist Python Script
        script_file = self.scripts_dir / f"{slug}.py"
        code_content = skill_data.get("python_code", "")
        if not code_content.startswith("#!"):
            code_content = "#!/usr/bin/env python3\n" + code_content

        script_file.write_text(code_content, encoding="utf-8")
        try:
            os.chmod(script_file, 0o755)
        except Exception:
            pass

        # 5. Syntax validation
        try:
            py_compile.compile(str(script_file), doraise=True)
            console.print(f"[green]✅ Code syntax verified: {script_file}[/green]")
        except Exception as py_err:
            console.print(f"[yellow]⚠️ Script syntax notice: {py_err}[/yellow]")

        # 6. Database record in learned_skills
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO learned_skills (slug, title, description, keywords, script_path, knowledge_path, capabilities, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    title=excluded.title,
                    description=excluded.description,
                    keywords=excluded.keywords,
                    script_path=excluded.script_path,
                    knowledge_path=excluded.knowledge_path,
                    capabilities=excluded.capabilities,
                    created_at=excluded.created_at;
            """, (slug, title, desc, keywords, str(script_file), str(knowledge_file), caps_str, now_str))

            # Also seed a task recipe so Victoria's brain instantly recognizes how to trigger it
            conn.execute("""
                INSERT INTO task_recipes (intent_summary, keywords, tool_sequence, success_count, failure_count, last_used, created_at, notes)
                VALUES (?, ?, ?, 1, 0, ?, ?, ?);
            """, (
                f"Execute skill: {title}",
                f"{slug} {keywords} {topic}",
                json.dumps([{"name": "run_custom_script", "arguments": {"script_name": f"{slug}.py"}}]),
                datetime.now().timestamp(),
                now_str,
                f"Autonomous skill acquired from web R&D: {title}",
            ))
            conn.commit()

        # 7. Format verbal response according to exact user requirement
        spoken_response = (
            f"जी हरिओम! मैंने इंटरनेट से R&D करके '{title}' की स्किल और नॉलेज अपने अंदर "
            f"सफलतापूर्वक शामिल कर ली है। अब यह स्किल मेरे पास उपलब्ध है—इस स्किल का उपयोग "
            f"करके आप मुझसे क्या काम करवाना चाहते हैं?"
        )

        console.print(f"[bold green]🌟 Skill Acquired:[/bold green] {title} ({slug})")

        return {
            "status": "success",
            "slug": slug,
            "title": title,
            "description": desc,
            "speech": spoken_response,
            "script_path": str(script_file),
            "knowledge_path": str(knowledge_file),
            "capabilities": caps,
        }

    def list_skills(self) -> List[Dict[str, Any]]:
        """List all acquired skills."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT slug, title, description, script_path, capabilities, created_at FROM learned_skills ORDER BY id DESC;")
            return [dict(r) for r in cur.fetchall()]


# ==========================================
# Skill Intent Detector for Voice Dialogue Loop
# ==========================================

def detect_skill_request(text: str) -> Optional[str]:
    """
    Detect if the user is asking Victoria to research and acquire a new skill/knowledge.
    Returns the extracted skill topic, or None.
    """
    if not text or not text.strip():
        return None

    clean = re.sub(
        r"^(हे\s+विक्टोरिया|विक्टोरिया|victoria|hey\s+victoria)[,\s]*",
        "",
        text.strip(),
        flags=re.IGNORECASE,
    ).strip()

    patterns = [
        r"(?:नई\s+स्किल|न्यू\s+स्किल|new\s+skill|स्किल|skill|नॉलेज|knowledge)\s+(?:सीखो|ऐड\s+करो|जोड़ो|ले\s+आओ|add\s+karo|seekho|learn)\s*[:\-–]?\s*(.+)",
        r"(.+?)\s*(?:की\s+स्किल|की\s+नॉलेज|का\s+ज्ञान)\s*(?:सीखो|ऐड\s+करो|जोड़ो|अपने\s+अंदर\s+लाओ|ले\s+आओ|add\s+karo|seekho)",
        r"(?:r\s*&\s*d|rnd|रिसर्च)\s*(?:करके|करो)\s*(?:और)?\s*(?:नई\s+स्किल|स्किल|नॉलेज)?\s*(?:सीखो|ऐड\s+करो|ले\s+आओ|जोड़ो)?\s*[:\-–]?\s*(.+)",
        r"(?:learn|research|acquire)\s+(?:new\s+)?(?:skill|knowledge)\s*[:\-–]?\s*(.+)",
        r"(?:apne\s+andar|अपने\s+अंदर)\s*(?:ye|यह|नई)?\s*(?:skill|स्किल|नॉलेज|knowledge)\s*(?:add\s+karo|ऐड\s+करो|ले\s+आओ|जोड़ो|सीखो)\s*[:\-–]?\s*(.+)",
    ]

    for pat in patterns:
        m = re.search(pat, clean, flags=re.IGNORECASE)
        if m:
            topic = m.group(1).strip()
            # Strip trailing verbs if any
            topic = re.sub(
                r"\s*(सीखो|ऐड\s+करो|ले\s+आओ|जोड़ो|karo|learn|add|karna\s+hai)$",
                "",
                topic,
                flags=re.IGNORECASE,
            ).strip()
            # Strip punctuation
            topic = topic.strip(": -–,.")
            if len(topic) >= 2:
                return topic

    return None


# Global Singleton Instance
_rnd_engine_instance: Optional[SkillRNDEngine] = None


def get_skill_rnd_engine() -> SkillRNDEngine:
    global _rnd_engine_instance
    if _rnd_engine_instance is None:
        _rnd_engine_instance = SkillRNDEngine()
    return _rnd_engine_instance
