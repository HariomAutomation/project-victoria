"""
Victoria - Daily Work Journal & Continuity Tools
Enables Victoria to log tasks, query today's work journal, update checkpoints,
and resume work exactly from where it was left off across any AI model.
"""

from victoria.brain.daily_work_logger import get_daily_work_logger


def log_daily_task(
    title: str,
    description: str,
    status: str = "completed",
    tools_used: str = "",
    next_steps: str = "",
    project: str = "PROJECT VICTORIA",
) -> str:
    """
    Log a completed, ongoing, or pending task into Hariom's daily work ledger.
    Works 100% locally in SQLite and exports to Markdown.

    Args:
        title: Short descriptive title of the task
        description: Detailed summary of what was accomplished or attempted
        status: 'completed', 'in_progress', 'pending', or 'paused'
        tools_used: Names of tools or scripts utilized
        next_steps: Recommended next steps or pending items
        project: Project name (default: 'PROJECT VICTORIA')
    """
    logger = get_daily_work_logger()
    task_id = logger.log_work(
        title=title,
        description=description,
        status=status,
        tools_used=tools_used,
        next_steps=next_steps,
        project=project,
    )
    return f"✅ कार्य दैनिकी में सफलतापूर्वक दर्ज किया गया (Task ID: {task_id}): '{title}' [{status.upper()}]"


def get_daily_work_journal(date: str = "") -> str:
    """
    Get the complete daily work journal and activity log for today or a specific date.

    Args:
        date: Date in YYYY-MM-DD format (leave empty for today)
    """
    logger = get_daily_work_logger()
    summary = logger.get_daily_summary(date if date.strip() else None)

    tasks = summary.get("tasks", [])
    ckpt = summary.get("last_checkpoint")

    lines = [
        f"📅 [दैनिक कार्य दैनिकी — {summary['date']} (कुल कार्य: {summary['total_tasks']})]",
    ]

    if ckpt:
        lines.extend([
            "📍 अंतिम कार्य स्थिति (Where We Left Off):",
            f"  • प्रोजेक्ट: {ckpt.get('current_project', 'PROJECT VICTORIA')}",
            f"  • अंतिम कार्य: {ckpt.get('last_task')}",
            f"  • स्थिति: {ckpt.get('where_we_left_off')}",
            f"  • अगले कदम: {ckpt.get('next_planned_steps')}",
            "",
        ])

    if not tasks:
        lines.append("आज अभी तक कोई कार्य दर्ज नहीं हुआ है।")
    else:
        lines.append("📝 दर्ज किए गए कार्य:")
        for t in tasks:
            status_icon = "✅" if t["status"] == "completed" else "⏳"
            lines.append(
                f"  {status_icon} [{t['time_str']}] {t['title']} ({t['status'].upper()})\n"
                f"    विवरण: {t['description'][:120]}"
            )

    return "\n".join(lines)


def get_last_work_checkpoint() -> str:
    """
    Check where work was left off and what the next steps are.
    Call this when Hariom asks 'हम क्या कर रहे थे?', 'जहाँ छोड़ा था वहाँ से शुरू करो',
    or wants to resume previous work.
    """
    logger = get_daily_work_logger()
    ckpt = logger.get_last_checkpoint()
    if not ckpt:
        return "अभी कोई पिछला कार्य चेकपॉइंट दर्ज नहीं है।"

    return (
        f"📍 [अंतिम कार्य स्थिति (Where We Left Off)]:\n"
        f"• प्रोजेक्ट: {ckpt.get('current_project', 'PROJECT VICTORIA')}\n"
        f"• अंतिम कार्य: {ckpt.get('last_task')}\n"
        f"• स्थिति / प्रगति: {ckpt.get('where_we_left_off')}\n"
        f"• अगले नियोजित कदम: {ckpt.get('next_planned_steps')}\n"
        f"• अंतिम सक्रियता: {ckpt.get('date')} {ckpt.get('time_str')} (मॉडल: {ckpt.get('model_used', '-')})"
    )


def save_work_checkpoint(
    last_task: str,
    where_we_left_off: str,
    next_planned_steps: str = "",
    project: str = "PROJECT VICTORIA",
    active_files: str = "",
) -> str:
    """
    Manually save or update the 'Where We Left Off' checkpoint.

    Args:
        last_task: Title of the current/last task
        where_we_left_off: Clear description of the exact state where work is stopping
        next_planned_steps: What to do when resuming work
        project: Project name
        active_files: Comma-separated list of active files
    """
    logger = get_daily_work_logger()
    ckpt_id = logger.set_checkpoint(
        last_task=last_task,
        where_we_left_off=where_we_left_off,
        next_planned_steps=next_planned_steps,
        project=project,
        active_files=active_files,
    )
    logger.export_daily_journal_markdown()
    return f"📍 कार्य चेकपॉइंट सफलतापूर्वक सहेजा गया (ID: {ckpt_id}): '{last_task}' पर रुका हुआ काम सुरक्षित है।"


def query_work_by_date_time(query: str, date: str = "", time: str = "") -> str:
    """
    Query what work, tasks, or conversations were recorded at a specific date and time.
    Call this when Hariom asks questions like:
      - '16 तारीख को 2:30 बजे हमने क्या किया था?'
      - 'आज 3 बजे क्या हुआ था?'
      - 'कल क्या-क्या काम हुआ था?'

    Args:
        query: The natural query in Hindi or English
        date: Specific date YYYY-MM-DD (optional)
        time: Specific time HH:MM (optional)
    """
    logger = get_daily_work_logger()
    target_d = date.strip() if date and date.strip() else None
    res = logger.query_work_by_date_time(query=query, target_date=target_d)
    return res.get("speech", "कोई कार्य नहीं मिला।")

