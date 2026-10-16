"""
Victoria - Terminal Command Execution Tool
Safely execute shell commands with timeout and output capture.
"""

import subprocess
from victoria.config import get_config


def run_command(command: str, timeout: int = 30) -> str:
    """
    Execute a shell command and return the output.

    Args:
        command: Shell command to execute
        timeout: Maximum execution time in seconds

    Returns:
        Command output (stdout + stderr) or error message
    """
    cfg = get_config()

    # Safety check for dangerous commands
    dangerous_patterns = cfg.get("tools.dangerous_commands", [])
    cmd_lower = command.lower().strip()

    for pattern in dangerous_patterns:
        if pattern.lower() in cmd_lower:
            return (
                f"⚠️ DANGEROUS COMMAND DETECTED: '{command}' matches pattern '{pattern}'. "
                f"This command requires explicit confirmation from the owner. "
                f"If you're sure, the owner must verbally confirm."
            )

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=None,  # Use current environment
        )

        output = ""
        if result.stdout:
            output += result.stdout.strip()
        if result.stderr:
            if output:
                output += "\n--- stderr ---\n"
            output += result.stderr.strip()

        if result.returncode != 0:
            output += f"\n[Exit code: {result.returncode}]"

        return output if output else f"✅ Command completed (exit code: {result.returncode})"

    except subprocess.TimeoutExpired:
        return f"⏱️ Command timed out after {timeout} seconds: {command}"
    except Exception as e:
        return f"❌ Error executing command: {str(e)}"
