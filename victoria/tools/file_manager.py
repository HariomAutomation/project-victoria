"""
Victoria - File Manager Tool
Search, read, write, list, and create files and directories.
"""

import os
import subprocess


def search_files(pattern: str, directory: str = None, max_results: int = 20) -> str:
    """
    Search for files by name pattern using find command.
    
    Args:
        pattern: Filename pattern (e.g., '*.py', 'config*', 'report.pdf')
        directory: Directory to search in (default: home directory)
        max_results: Maximum number of results
    """
    if directory is None:
        directory = os.path.expanduser("~")

    try:
        result = subprocess.run(
            ["find", directory, "-maxdepth", "5", "-iname", pattern,
             "-not", "-path", "*/\\.git/*",
             "-not", "-path", "*/node_modules/*",
             "-not", "-path", "*/\\.cache/*"],
            capture_output=True, text=True, timeout=15,
        )

        files = result.stdout.strip().split("\n")
        files = [f for f in files if f][:max_results]

        if files:
            return f"Found {len(files)} files:\n" + "\n".join(f"  📄 {f}" for f in files)
        else:
            return f"No files found matching '{pattern}' in {directory}"

    except subprocess.TimeoutExpired:
        return "⏱️ Search timed out. Try a more specific directory."
    except Exception as e:
        return f"❌ Search error: {str(e)}"


def read_file(filepath: str, max_lines: int = 100) -> str:
    """
    Read the contents of a text file.
    
    Args:
        filepath: Path to the file
        max_lines: Maximum number of lines to read
    """
    filepath = os.path.expanduser(filepath)

    if not os.path.exists(filepath):
        return f"❌ File not found: {filepath}"

    if not os.path.isfile(filepath):
        return f"❌ Not a file: {filepath}"

    # Check file size
    size = os.path.getsize(filepath)
    if size > 1_000_000:  # 1MB
        return f"⚠️ File too large ({size/1_000_000:.1f}MB). Use 'head' or 'tail' command instead."

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[:max_lines]

        content = "".join(lines)
        total_lines = len(lines)
        truncated = total_lines >= max_lines

        header = f"📄 {filepath} ({total_lines} lines"
        if truncated:
            header += f", showing first {max_lines}"
        header += "):\n"

        return header + content

    except Exception as e:
        return f"❌ Error reading file: {str(e)}"


def write_file(filepath: str, content: str) -> str:
    """
    Write content to a file (creates parent directories if needed).
    
    Args:
        filepath: Path to write to
        content: Content to write
    """
    filepath = os.path.expanduser(filepath)

    try:
        # Create parent directories
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        size = os.path.getsize(filepath)
        return f"✅ Written to {filepath} ({size} bytes)"

    except PermissionError:
        return f"❌ Permission denied: {filepath}"
    except Exception as e:
        return f"❌ Error writing file: {str(e)}"


def list_directory(path: str = None) -> str:
    """
    List files and directories in a path.
    
    Args:
        path: Directory path (default: current directory)
    """
    if path is None:
        path = os.path.expanduser("~")
    else:
        path = os.path.expanduser(path)

    if not os.path.exists(path):
        return f"❌ Path not found: {path}"

    if not os.path.isdir(path):
        return f"❌ Not a directory: {path}"

    try:
        entries = sorted(os.listdir(path))
        dirs = []
        files = []

        for entry in entries:
            full_path = os.path.join(path, entry)
            if entry.startswith("."):
                continue  # Skip hidden files by default

            if os.path.isdir(full_path):
                dirs.append(f"  📁 {entry}/")
            else:
                size = os.path.getsize(full_path)
                size_str = _format_size(size)
                files.append(f"  📄 {entry} ({size_str})")

        result = f"📂 {path}:\n"
        if dirs:
            result += "Directories:\n" + "\n".join(dirs[:30]) + "\n"
        if files:
            result += "Files:\n" + "\n".join(files[:30]) + "\n"
        if not dirs and not files:
            result += "  (empty directory)"

        return result

    except PermissionError:
        return f"❌ Permission denied: {path}"
    except Exception as e:
        return f"❌ Error listing directory: {str(e)}"


def create_directory(path: str) -> str:
    """Create a directory (including parent directories)."""
    path = os.path.expanduser(path)

    try:
        os.makedirs(path, exist_ok=True)
        return f"✅ Directory created: {path}"
    except PermissionError:
        return f"❌ Permission denied: {path}"
    except Exception as e:
        return f"❌ Error creating directory: {str(e)}"


def _format_size(size: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}" if unit != "B" else f"{size}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
