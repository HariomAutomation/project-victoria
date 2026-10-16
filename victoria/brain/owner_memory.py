"""
Victoria - Local Offline Owner Memory Vault (मालिक की लोकल ऑफ़लाइन स्मृति भंडार)
100% local, zero-cloud, privacy-preserving persistent episodic and semantic memory
powered by SQLite + FTS5 with Unicode tokenization. Operates seamlessly offline.
"""

import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.console import Console

from victoria.config import PROJECT_ROOT

console = Console()

DB_DIR = PROJECT_ROOT / "data" / "memory"
DB_PATH = DB_DIR / "victoria.db"
EXPORT_MD_PATH = DB_DIR / "owner_memories_archive.md"


class OwnerMemoryVault:
    """
    Local Offline Memory Engine for the Owner.

    Features:
      - 100% Local SQLite storage with WAL mode for speed and reliability.
      - SQLite FTS5 (Full-Text Search) with Unicode61 tokenizer for Hindi & English.
      - Categorized memories: facts, preferences, intentions, projects, events, notes.
      - Importance ranking (1-5) and access frequency tracking.
      - Fast semantic-like recall for AI prompts with zero network requests.
      - Offline export to human-readable Markdown.
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
        """Create owner_memories table and FTS5 search index."""
        with self._get_connection() as conn:
            # 1. Main memories table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS owner_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'fact',
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    importance INTEGER NOT NULL DEFAULT 3,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    last_recalled REAL
                );
            """)

            # 2. Indexes for fast queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_category ON owner_memories(category);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_importance ON owner_memories(importance DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_timestamp ON owner_memories(timestamp DESC);")

            # 3. FTS5 Virtual Table for full-text offline search in Hindi & English
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS owner_memories_fts USING fts5(
                    title,
                    content,
                    tags,
                    content='owner_memories',
                    content_rowid='id',
                    tokenize='unicode61'
                );
            """)

            # 4. Triggers to keep FTS index synchronized
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_memories_ai AFTER INSERT ON owner_memories BEGIN
                    INSERT INTO owner_memories_fts(rowid, title, content, tags)
                    VALUES (new.id, new.title, new.content, new.tags);
                END;
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_memories_ad AFTER DELETE ON owner_memories BEGIN
                    INSERT INTO owner_memories_fts(owner_memories_fts, rowid, title, content, tags)
                    VALUES('delete', old.id, old.title, old.content, old.tags);
                END;
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_memories_au AFTER UPDATE ON owner_memories BEGIN
                    INSERT INTO owner_memories_fts(owner_memories_fts, rowid, title, content, tags)
                    VALUES('delete', old.id, old.title, old.content, old.tags);
                    INSERT INTO owner_memories_fts(rowid, title, content, tags)
                    VALUES (new.id, new.title, new.content, new.tags);
                END;
            """)

            conn.commit()

        # Seed initial memories if table is empty
        self._seed_initial_memories_if_empty()

    def _seed_initial_memories_if_empty(self):
        """Seed foundational knowledge about the owner on first run."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM owner_memories;")
            count = cur.fetchone()[0]
            if count == 0:
                initial_seeds = [
                    {
                        "category": "preference",
                        "title": "प्राथमिक भाषा और संवाद शैली",
                        "content": "हरिओम को स्वाभाविक और आत्मीय हिंदी (Hinglish) में बात करना पसंद है। विक्टोरिया उन्हें हमेशा आदर और अपनेपन से 'हरिओम' या 'हरिओम जी' कहकर ही संबोधित करती है।",
                        "tags": "भाषा, हिंदी, लहज़ा",
                        "importance": 5,
                    },
                    {
                        "category": "preference",
                        "title": "स्वायत्त कार्यशैली (Autonomy)",
                        "content": "मालिक को असिस्टेंट द्वारा बिना बार-बार अनुमति मांगे पूरे multi-step कार्य स्वायत्त रूप से पूरा करना पसंद है।",
                        "tags": "autonomy, execution, workstyle",
                        "importance": 5,
                    },
                    {
                        "category": "intention",
                        "title": "प्रोजेक्ट विक्टोरिया विज़न",
                        "content": "मालिक का इरादा विक्टोरिया को एक सुपर-इंटेलिजेंट, लिनक्स-इंटीग्रेटेड, डिजिटल ट्विन और REA रिवर्स इंजीनियरिंग पावरहाउस बनाना है।",
                        "tags": "victoria, vision, project, digital_twin",
                        "importance": 5,
                    },
                    {
                        "category": "project",
                        "title": "REA - Reverse Engineer Anything",
                        "content": "मालिक चाहते हैं कि सिस्टम की हर ऐप, वेबसाइट, डेटाबेस और डिवाइस को आसानी से रिवर्स इंजीनियर और क्लोन किया जा सके।",
                        "tags": "rea, reverse_engineering, teardown",
                        "importance": 4,
                    },
                    {
                        "category": "preference",
                        "title": "टोकन व रिसोर्स ऑप्टिमाइजेशन",
                        "content": "मालिक को टोकन की बचत पसंद है, इसलिए LeanToken (morluto/leantoken) का उपयोग करके कोड और फाइलों को कंप्रेस किया जाता है।",
                        "tags": "leantoken, tokens, efficiency",
                        "importance": 4,
                    },
                    {
                        "category": "fact",
                        "title": "सिस्टम पर्यावरण",
                        "content": "मालिक का ऑपरेटिंग सिस्टम Ubuntu Linux 26.04 LTS (x86_64) है। सभी कार्य सीधे लोकल मशीन पर निष्पादित होते हैं।",
                        "tags": "linux, ubuntu, os, environment",
                        "importance": 4,
                    }
                ]
                for seed in initial_seeds:
                    self.store(
                        content=seed["content"],
                        category=seed["category"],
                        title=seed["title"],
                        tags=seed["tags"],
                        importance=seed["importance"],
                    )
                console.print(f"[green]✅ Seeded {len(initial_seeds)} foundational local owner memories[/green]")

    def store(
        self,
        content: str,
        category: str = "fact",
        title: str = "",
        tags: str = "",
        importance: int = 3,
    ) -> int:
        """
        Store a new memory locally.

        Args:
            content: The memory text / description
            category: 'fact', 'preference', 'intention', 'project', 'event', 'note'
            title: Short title or subject (auto-generated if omitted)
            tags: Comma-separated tags
            importance: 1 (minor) to 5 (critical core identity)

        Returns:
            The ID of the inserted memory
        """
        content = content.strip()
        if not content:
            raise ValueError("Memory content cannot be empty")

        if not title:
            # Auto-generate title from first 50 chars of content
            first_line = content.split("\n")[0].strip()
            title = first_line[:50] + ("..." if len(first_line) > 50 else "")

        now_ts = time.time()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        importance = max(1, min(5, int(importance)))

        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO owner_memories 
                   (timestamp, created_at, category, title, content, tags, importance, access_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0);""",
                (now_ts, now_str, category.lower(), title, content, tags, importance),
            )
            conn.commit()
            mem_id = cursor.lastrowid

        self.export_to_markdown()
        return mem_id

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Offline search across owner memories using FTS5 with fallback to LIKE.
        Completely local with zero network calls.
        """
        query = query.strip()
        if not query:
            return self.list_memories(category=category, limit=limit)

        results = []
        with self._get_connection() as conn:
            # 1. Attempt FTS5 Full-Text Match
            fts_query = query.replace("'", " ").replace('"', ' ')
            # Clean non-alphanumeric except spaces for FTS tokens
            fts_terms = [t for t in fts_query.split() if len(t) > 1]

            if fts_terms:
                fts_expr = " OR ".join([f'"{t}"*' for t in fts_terms])
                try:
                    sql = """
                        SELECT m.*, rank
                        FROM owner_memories_fts f
                        JOIN owner_memories m ON f.rowid = m.id
                        WHERE owner_memories_fts MATCH ?
                    """
                    params = [fts_expr]
                    if category:
                        sql += " AND m.category = ?"
                        params.append(category.lower())
                    sql += " ORDER BY rank, m.importance DESC LIMIT ?;"
                    params.append(limit)

                    rows = conn.execute(sql, params).fetchall()
                    for r in rows:
                        results.append(dict(r))
                except Exception:
                    # Fallback if FTS query syntax error
                    pass

            # 2. Fallback to Substring LIKE if FTS gave few or zero results
            if len(results) < limit:
                existing_ids = {r["id"] for r in results}
                like_sql = """
                    SELECT * FROM owner_memories
                    WHERE (content LIKE ? OR title LIKE ? OR tags LIKE ?)
                """
                like_params = [f"%{query}%", f"%{query}%", f"%{query}%"]
                if category:
                    like_sql += " AND category = ?"
                    like_params.append(category.lower())
                like_sql += " ORDER BY importance DESC, timestamp DESC LIMIT ?;"
                like_params.append(limit - len(results))

                rows = conn.execute(like_sql, like_params).fetchall()
                for r in rows:
                    if r["id"] not in existing_ids:
                        results.append(dict(r))

            # 3. Update access count & recall timestamp
            if results:
                ids = [r["id"] for r in results]
                placeholders = ",".join(["?"] * len(ids))
                conn.execute(
                    f"""UPDATE owner_memories 
                        SET access_count = access_count + 1, last_recalled = ?
                        WHERE id IN ({placeholders});""",
                    [time.time()] + ids,
                )
                conn.commit()

        return results

    def get_relevant_context(self, user_query: str, max_items: int = 4) -> str:
        """
        Retrieve relevant local memories for a given user query to inject
        into Victoria's active working memory. Works 100% offline.
        """
        matches = self.search(user_query, limit=max_items)
        if not matches:
            return ""

        lines = ["=== 🧠 मालिक की प्रासंगिक लोकल स्मृति (RECALLED OWNER MEMORIES) ==="]
        for m in matches:
            cat_icon = {
                "preference": "💖",
                "fact": "📌",
                "intention": "🎯",
                "project": "🚀",
                "event": "📅",
                "note": "📝"
            }.get(m["category"], "•")
            lines.append(f"{cat_icon} [{m['category'].upper()}] {m['title']}: {m['content']}")
        lines.append("==================================================================")
        return "\n".join(lines)

    def list_memories(
        self,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List stored memories with pagination."""
        with self._get_connection() as conn:
            if category:
                rows = conn.execute(
                    """SELECT * FROM owner_memories 
                       WHERE category = ? 
                       ORDER BY importance DESC, timestamp DESC 
                       LIMIT ? OFFSET ?;""",
                    (category.lower(), limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM owner_memories 
                       ORDER BY importance DESC, timestamp DESC 
                       LIMIT ? OFFSET ?;""",
                    (limit, offset),
                ).fetchall()
            return [dict(r) for r in rows]

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory by ID."""
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM owner_memories WHERE id = ?;", (memory_id,))
            conn.commit()
            deleted = cur.rowcount > 0

        if deleted:
            self.export_to_markdown()
        return deleted

    def update_memory(
        self,
        memory_id: int,
        content: Optional[str] = None,
        title: Optional[str] = None,
        category: Optional[str] = None,
        importance: Optional[int] = None,
        tags: Optional[str] = None,
    ) -> bool:
        """Update fields of an existing memory."""
        fields = []
        params = []
        if content is not None:
            fields.append("content = ?")
            params.append(content.strip())
        if title is not None:
            fields.append("title = ?")
            params.append(title.strip())
        if category is not None:
            fields.append("category = ?")
            params.append(category.lower().strip())
        if importance is not None:
            fields.append("importance = ?")
            params.append(max(1, min(5, int(importance))))
        if tags is not None:
            fields.append("tags = ?")
            params.append(tags.strip())

        if not fields:
            return False

        params.append(memory_id)
        sql = f"UPDATE owner_memories SET {', '.join(fields)} WHERE id = ?;"

        with self._get_connection() as conn:
            cur = conn.execute(sql, params)
            conn.commit()
            updated = cur.rowcount > 0

        if updated:
            self.export_to_markdown()
        return updated

    def get_stats(self) -> Dict[str, Any]:
        """Get stats on total memories, categories, and database size."""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM owner_memories;").fetchone()[0]
            cats = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM owner_memories GROUP BY category;"
            ).fetchall()
            db_size_kb = round(self.db_path.stat().st_size / 1024, 1) if self.db_path.exists() else 0

            return {
                "total_memories": total,
                "categories": {r["category"]: r["cnt"] for r in cats},
                "db_size_kb": db_size_kb,
                "db_path": str(self.db_path),
                "offline_mode": True,
            }

    def export_to_markdown(self):
        """Export all local memories to a clean Markdown file for human inspection."""
        memories = self.list_memories(limit=500)
        lines = [
            "# 🧠 मालिक की लोकल स्मृति भंडार (Owner Local Memory Vault)",
            "",
            "> **\"यह फ़ाइल 100% ऑफ़लाइन, लोकल SQLite डेटाबेस से सीधे एक्सपोर्ट की गई है। बिना इंटरनेट के भी यह पूरी तरह काम करती है।\"**",
            "",
            f"- **कुल स्मृतियाँ:** {len(memories)}",
            f"- **डेटाबेस पथ:** `{self.db_path}`",
            f"- **अंतिम अपडेट:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
            "",
            "---",
            ""
        ]

        # Group by category
        by_category: Dict[str, List[Dict[str, Any]]] = {}
        for m in memories:
            cat = m["category"]
            by_category.setdefault(cat, []).append(m)

        category_labels = {
            "preference": "💖 पसंद एवं प्राथमिकताएं (Preferences)",
            "intention": "🎯 इरादे एवं मिशन (Intentions & Missions)",
            "fact": "📌 तथ्य एवं व्यक्तिगत जानकारी (Facts & Profile)",
            "project": "🚀 प्रोजेक्ट्स एवं कार्य (Projects)",
            "event": "📅 घटनाक्रम एवं इतिहास (Timeline & Events)",
            "note": "📝 निजी नोट्स एवं निर्देश (Notes)"
        }

        for cat, items in by_category.items():
            heading = category_labels.get(cat, f"📁 {cat.title()}")
            lines.append(f"## {heading}")
            lines.append("")
            for it in items:
                stars = "⭐" * it["importance"]
                lines.append(f"### {it['title']}  {stars}")
                lines.append(f"- **विवरण:** {it['content']}")
                if it.get("tags"):
                    lines.append(f"- **टैग्स:** `{it['tags']}`")
                lines.append(f"- **दर्ज दिनांक:** `{it['created_at']}` | **रिकॉल गणना:** `{it['access_count']}` बार")
                lines.append("")

        with open(EXPORT_MD_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


# Global Singleton Instance
_owner_vault_instance: Optional[OwnerMemoryVault] = None


def get_owner_vault() -> OwnerMemoryVault:
    """Get or initialize the global OwnerMemoryVault instance."""
    global _owner_vault_instance
    if _owner_vault_instance is None:
        _owner_vault_instance = OwnerMemoryVault()
    return _owner_vault_instance
