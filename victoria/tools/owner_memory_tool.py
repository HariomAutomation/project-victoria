"""
Victoria - Owner Memory Vault Tools
Enables Victoria to store, search, list, and delete local offline memories about the owner.
Works completely offline without external APIs or cloud services.
"""

from victoria.brain.owner_memory import get_owner_vault


def save_owner_memory(
    content: str,
    category: str = "fact",
    title: str = "",
    tags: str = "",
    importance: int = 3,
) -> str:
    """
    Save a new personal memory about the owner to the local offline database.
    Works 100% offline.

    Args:
        content: The text describing the memory, fact, preference, or goal
        category: 'fact', 'preference', 'intention', 'project', 'event', or 'note'
        title: Short title or summary for the memory (optional)
        tags: Comma-separated keywords/tags (optional)
        importance: 1 to 5 (5 = critical core identity)
    """
    vault = get_owner_vault()
    mem_id = vault.store(
        content=content,
        category=category,
        title=title,
        tags=tags,
        importance=importance,
    )
    return f"✅ लोकल मेमोरी सफलतापूर्वक सहेजी गई (ID: {mem_id}): [{category}] {title or content[:40]}"


def search_owner_memory(query: str, category: str = "") -> str:
    """
    Search local offline memories about the owner using SQLite FTS5 full-text search.
    Works completely offline with zero internet access.

    Args:
        query: Search keywords or query in Hindi or English
        category: Filter by category (optional: 'fact', 'preference', 'intention', 'project', etc.)
    """
    vault = get_owner_vault()
    cat = category.strip() if category else None
    results = vault.search(query=query, category=cat, limit=6)

    if not results:
        return f"🔍 '{query}' से संबंधित कोई लोकल मेमोरी नहीं मिली।"

    lines = [f"🔍 [लोकल ऑफलाइन मेमोरी परिणाम: '{query}']"]
    for r in results:
        stars = "⭐" * r["importance"]
        lines.append(
            f"• [ID: {r['id']}] [{r['category'].upper()}] {r['title']} ({stars})\n"
            f"  विवरण: {r['content']}\n"
            f"  दिनांक: {r['created_at']} | रिकॉल: {r['access_count']} बार"
        )
    return "\n\n".join(lines)


def list_owner_memories(category: str = "", limit: int = 10) -> str:
    """
    List stored offline memories of the owner, ordered by importance and recency.
    """
    vault = get_owner_vault()
    cat = category.strip() if category else None
    memories = vault.list_memories(category=cat, limit=limit)

    if not memories:
        return "लोकल मेमोरी डेटाबेस में अभी कोई स्मृति नहीं है।"

    lines = [f"📋 [मालिक की सहेजी गई लोकल स्मृतियाँ (कुल: {len(memories)})]:"]
    for m in memories:
        stars = "⭐" * m["importance"]
        lines.append(
            f"• [ID: {m['id']}] [{m['category'].upper()}] {m['title']} ({stars})\n"
            f"  {m['content']}"
        )
    return "\n\n".join(lines)


def delete_owner_memory(memory_id: int) -> str:
    """
    Delete a specific local memory by its ID.
    """
    vault = get_owner_vault()
    success = vault.delete_memory(memory_id=memory_id)
    if success:
        return f"🗑️ मेमोरी ID {memory_id} को लोकल डेटाबेस से हटा दिया गया।"
    return f"❌ मेमोरी ID {memory_id} नहीं मिली।"
