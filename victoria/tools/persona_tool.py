"""
Victoria - Persona & Digital Twin Tools
Exposes tools for Victoria to inspect, record, and maintain the owner's profile and preferences.
"""

from victoria.brain.persona import get_persona_engine


def view_owner_persona() -> str:
    """
    View the current Owner Persona Dossier & Digital Twin profile.
    Shows what Victoria has learned about the owner's likes, dislikes,
    intentions, and habits.
    """
    engine = get_persona_engine()
    identity = engine.profile.get("owner_identity", {})
    prefs = engine.profile.get("preferences", {})
    goals = engine.profile.get("intentions_and_goals", {})

    report = (
        f"🧬 [हरिओम जी की डिजिटल हमशक्ल प्रोफ़ाइल]\n"
        f"• कुल संवाद: {identity.get('interaction_count', 0)}\n"
        f"• मुख्य पसंद: {', '.join(prefs.get('likes', [])[:5])}\n"
        f"• मुख्य नापसंद: {', '.join(prefs.get('dislikes', [])[:4])}\n"
        f"• वर्तमान मिशन: {'; '.join(goals.get('current_missions', [])[:3])}\n"
        f"• अंतिम अपडेट: {identity.get('last_updated', '')}"
    )
    return report


def remember_owner_preference(category: str, detail: str) -> str:
    """
    Explicitly remember a fact, preference, intention, or dislike about the owner.
    Use this when the owner mentions what they like, what they want to achieve, or how they work.

    Args:
        category: 'like' (पसंद), 'dislike' (नापसंद), 'goal' (इरादा/मिशन), or 'tech' (तकनीक)
        detail: The specific preference or intention to remember
    """
    engine = get_persona_engine()
    res = engine.add_explicit_fact(category=category, detail=detail)
    return res


def get_owner_intentions() -> str:
    """
    Get the list of active missions, goals, and long-term intentions of the owner.
    """
    engine = get_persona_engine()
    goals = engine.profile.get("intentions_and_goals", {})
    missions = goals.get("current_missions", [])
    visions = goals.get("long_term_intentions", [])

    lines = ["🎯 [हरिओम जी के सक्रिय मिशन व इरादे]:"]
    for i, m in enumerate(missions, 1):
        lines.append(f"{i}. {m}")
    if visions:
        lines.append("\n🔮 [दूरगामी विज़न]:")
        for i, v in enumerate(visions, 1):
            lines.append(f"• {v}")
    return "\n".join(lines)
