"""
Victoria - Experiential Learning & Skills Tools
Allows Victoria to explicitly remember lessons, register task shortcuts,
and view her self-evolution progress.
"""

from victoria.brain.experience import get_experience_engine


def remember_learned_rule(rule: str, trigger: str = "", rule_type: str = "correction") -> str:
    """
    Explicitly remember a learned rule, correction, or preferred workflow.
    
    Args:
        rule: The rule or behavior to remember (e.g. 'Always use Chrome for music')
        trigger: The keywords or intent that should trigger this rule
        rule_type: 'correction', 'preference', 'shortcut', or 'guardrail'
    """
    engine = get_experience_engine()
    engine.add_rule(
        trigger=trigger or rule[:30],
        rule_instruction=rule,
        rule_type=rule_type,
        learned_from="AI Autonomous Learning",
    )
    return f"✅ मैंने नया नियम सीख लिया है और याद रखूँगी: '{rule}'"


def view_learned_skills() -> dict:
    """
    View Victoria's learned task recipes, user rules, and assistant evolution level.
    """
    engine = get_experience_engine()
    return engine.get_stats()
