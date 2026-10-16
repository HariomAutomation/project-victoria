"""
Victoria - Conversation Memory
Persists conversations to SQLite for long-term memory and context.
"""

import sqlite3
import time
from pathlib import Path
from rich.console import Console

from victoria.config import get_config

console = Console()


class ConversationMemory:
    """
    Persistent conversation memory using SQLite.

    Stores all conversations with timestamps, model used, and tool results.
    Enables Victoria to remember past interactions and context.
    """

    def __init__(self):
        cfg = get_config()
        mem_cfg = cfg.memory_config
        self.enabled: bool = mem_cfg.get("enabled", True)
        db_path = mem_cfg.get("db_path", "data/memory/victoria.db")

        if not Path(db_path).is_absolute():
            from victoria.config import PROJECT_ROOT
            db_path = str(PROJECT_ROOT / db_path)

        self.db_path = db_path

        if self.enabled:
            self._init_db()

    def _init_db(self):
        """Initialize the SQLite database."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    model_used TEXT,
                    tool_name TEXT,
                    tool_args TEXT,
                    tool_result TEXT,
                    language TEXT,
                    speaker_similarity REAL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session ON conversations(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON conversations(timestamp)
            """)
            conn.commit()

        console.print(f"[green]✅ Memory database ready: {self.db_path}[/green]")

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        model_used: str = "",
        tool_name: str = "",
        tool_args: str = "",
        tool_result: str = "",
        language: str = "",
        speaker_similarity: float = 0.0,
    ):
        """Save a message to the database."""
        if not self.enabled:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO conversations 
                       (session_id, timestamp, role, content, model_used, 
                        tool_name, tool_args, tool_result, language, speaker_similarity)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (session_id, time.time(), role, content, model_used,
                     tool_name, tool_args, tool_result, language, speaker_similarity),
                )
                conn.commit()
        except Exception as e:
            console.print(f"[red]❌ Memory save error: {e}[/red]")

    def get_recent_messages(self, session_id: str, limit: int = 20) -> list[dict]:
        """Get recent messages from a session."""
        if not self.enabled:
            return []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """SELECT * FROM conversations 
                   WHERE session_id = ? 
                   ORDER BY timestamp DESC LIMIT ?""",
                (session_id, limit),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in reversed(rows)]

    def search_history(self, query: str, limit: int = 10) -> list[dict]:
        """Search conversation history by content."""
        if not self.enabled:
            return []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """SELECT * FROM conversations 
                   WHERE content LIKE ? 
                   ORDER BY timestamp DESC LIMIT ?""",
                (f"%{query}%", limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_session_summary(self, session_id: str) -> dict:
        """Get a summary of a conversation session."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """SELECT COUNT(*) as msg_count, 
                          MIN(timestamp) as start_time,
                          MAX(timestamp) as end_time
                   FROM conversations WHERE session_id = ?""",
                (session_id,),
            )
            row = cursor.fetchone()
            return {
                "message_count": row[0],
                "start_time": row[1],
                "end_time": row[2],
            }

    def get_stats(self) -> dict:
        """Get overall memory statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM conversations")
            total = cursor.fetchone()[0]
            cursor = conn.execute("SELECT COUNT(DISTINCT session_id) FROM conversations")
            sessions = cursor.fetchone()[0]
            return {"total_messages": total, "total_sessions": sessions}
