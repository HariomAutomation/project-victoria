"""
Victoria - Terminal Command Execution Tool
Safely execute shell commands with strict security locks for reboot,
shutdown, and destructive data loss prevention.
"""

import re
import subprocess
from typing import Optional
from victoria.config import get_config

# 1. HARD BLOCKED REBOOT & SHUTDOWN COMMANDS
# Under NO circumstances will Victoria ever execute OS reboot or shutdown.
# System reboot is permanently locked to prevent accidental crashes or data loss.
REBOOT_SHUTDOWN_PATTERNS = [
    r"\breboot\b",
    r"\bshutdown\b",
    r"\bpoweroff\b",
    r"\bhalt\b",
    r"\binit\s+[06]\b",
    r"\btelinit\s+[06]\b",
    r"\bsystemctl\s+(?:--\S+\s+)*(?:reboot|poweroff|halt|suspend|hibernate|hybrid-sleep|rescue|emergency)\b",
]

# 2. HARD BLOCKED DATA DESTRUCTION & FILE REMOVAL COMMANDS
# Strict security lock on removing or destroying files, directories, partition tables, or storage.
DATA_REMOVAL_PATTERNS = [
    r"\brm\s+",                            # rm command with arguments
    r"\brm\b$",                            # standalone rm
    r"\brmdir\b",                          # rmdir
    r"\bunlink\b",                         # unlink
    r"\bshred\b",                          # shred
    r"\bwipefs\b",                         # wipefs
    r"\bmkfs(?:\.\w+)?\b",                 # mkfs / mkfs.ext4 etc.
    r"\bdd\s+.*(?:of=/dev/|if=)",          # dd targeting devices
    r">\s*/dev/(?:sd|nvme|hd|vd|loop|mapper)",  # disk destruction redirection
    r"\bfind\b.*(?:-delete|-exec\s+rm)",   # find with -delete or -exec rm
    r"\btrash-put\b",                      # trash removal
    r"\btrash-empty\b",                    # trash emptying
    r"\btruncate\b.*(?:-s\s*0|--size\s*0|-s0|--size=0)",  # truncate to 0 wipe
    r"\bmv\b.*(?:\s+/dev/null|\s+/dev/zero)",              # moving to /dev/null
    r"os\.(?:remove|unlink|rmdir)",                        # python file deletion
    r"shutil\.(?:rmtree)",                                 # python recursive directory deletion
    r"Path\([^)]+\)\.unlink",                              # pathlib unlink
    r"(?:os\.system|subprocess)\b.*?['\"].*?(?:rm\s+|reboot|shutdown)", # shell injection tricks
    r"\bgit\s+clean\b",                                    # git clean -fd wipes untracked files
    r"(?:^|[;&|]\s*):\s*>\s*\S",                           # `: > file` truncation
    r"\bcp\s+(?:-f\s+)?/dev/null\s+\S",                    # copy /dev/null over a file (truncation)
]

REBOOT_LOCK_MESSAGE = (
    "🚫 सुरक्षा लॉक सक्रिय: हरिओम जी, आपके सिस्टम पर रीबूट और शटडाउन पूर्णतः लॉक (प्रतिबंधित) है "
    "ताकि आपका कोई भी डेटा नष्ट न हो। विक्टोरिया कभी भी आपके ऑपरेटिंग सिस्टम को रीबूट या बंद नहीं करेगी। "
    "यदि आप विक्टोरिया को रीस्टार्ट करना चाहते हैं, तो 'विक्टोरिया रीस्टार्ट करो' कहें।"
)

DATA_SECURITY_LOCK_MESSAGE = (
    "🛡️ डेटा सुरक्षा लॉक सक्रिय: हरिओम जी, आपके सिस्टम से किसी भी फ़ाइल या डेटा को हटाना (remove/delete) "
    "सुरक्षा नीति के तहत सख्त वर्जित है ताकि कोई डेटा डिलीट न हो। आपका डेटा 100% सुरक्षित है। कोई भी फ़ाइल हटाई नहीं गई है।"
)


def check_command_safety(command: str) -> Optional[str]:
    """
    Return the security-block message if the command violates the reboot or
    data-protection locks, otherwise None. Shared by the terminal tool, the IDE
    run endpoint, and the custom-script runner.
    """
    cmd_lower = (command or "").strip().lower()
    for pat in REBOOT_SHUTDOWN_PATTERNS:
        if re.search(pat, cmd_lower):
            return REBOOT_LOCK_MESSAGE
    for pat in DATA_REMOVAL_PATTERNS:
        if re.search(pat, cmd_lower):
            return DATA_SECURITY_LOCK_MESSAGE
    return None


def run_command(command: str, timeout: int = 30, confirmed: bool = False) -> str:
    """
    Execute a shell command with strict security validation.

    Args:
        command: Shell command to execute
        timeout: Maximum execution time in seconds
        confirmed: Set to True if Hariom has verbally confirmed execution of non-blocked dangerous commands

    Returns:
        Command output (stdout + stderr) or security block error message
    """
    cmd_strip = command.strip()
    cmd_lower = cmd_strip.lower()

    # 1 & 2. HARD SECURITY CHECKS: reboot/shutdown lock + data loss prevention
    blocked = check_command_safety(cmd_strip)
    if blocked:
        return blocked

    # 3. Configured dangerous commands check for other commands requiring confirmation
    cfg = get_config()
    dangerous_patterns = cfg.get("tools.dangerous_commands", [])

    if not confirmed:
        for pattern in dangerous_patterns:
            if pattern.lower() in cmd_lower:
                return (
                    f"⚠️ DANGEROUS COMMAND DETECTED: '{command}' matches pattern '{pattern}'. "
                    f"This command requires explicit verbal confirmation from Hariom. "
                    f"If Hariom has verbally confirmed, re-run with confirmed=True."
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

