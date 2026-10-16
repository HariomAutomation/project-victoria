"""
Victoria - Custom Scripts Tool
Run user-defined automation scripts located in scripts/custom or custom locations.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional
from victoria.config import PROJECT_ROOT

SCRIPTS_DIR = PROJECT_ROOT / "scripts" / "custom"


def list_custom_scripts() -> str:
    """
    List all custom user scripts available in the scripts/custom directory.

    Returns:
        List of available script names and descriptions.
    """
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    scripts = [f.name for f in SCRIPTS_DIR.iterdir() if f.is_file() and not f.name.startswith(".")]

    if not scripts:
        return "No custom scripts found in scripts/custom/."

    return "Available custom scripts:\n" + "\n".join(f"- {s}" for s in sorted(scripts))


def run_custom_script(script_name: str, args: Optional[str] = None, timeout: int = 60) -> str:
    """
    Execute a custom script located in scripts/custom.

    Args:
        script_name: The script filename (e.g. backup.sh, update.py)
        args: Optional arguments string to pass to the script
        timeout: Maximum execution time in seconds (default: 60)

    Returns:
        Output of the script execution.
    """
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    script_path = SCRIPTS_DIR / script_name

    if not script_path.exists():
        # Check if direct path was provided
        direct_path = Path(script_name)
        if direct_path.exists():
            script_path = direct_path
        else:
            return f"Script '{script_name}' not found in {SCRIPTS_DIR}."

    # Make executable if not already
    if not os.access(script_path, os.X_OK):
        try:
            os.chmod(script_path, 0o755)
        except Exception:
            pass

    cmd = [str(script_path)]
    if args:
        cmd.extend(args.split())

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = res.stdout.strip()
        if res.stderr:
            if output:
                output += "\n--- stderr ---\n"
            output += res.stderr.strip()
        if res.returncode != 0:
            output += f"\n[Exit code: {res.returncode}]"
        return output if output else "✅ Script finished successfully with no output."
    except subprocess.TimeoutExpired:
        return f"⏱️ Script execution timed out after {timeout} seconds."
    except Exception as e:
        return f"Error executing script: {e}"
