"""
Victoria - System Information Tool
Get detailed system information using psutil.
"""

import platform
import time


def get_system_info(info_type: str = "all") -> str:
    """
    Get system information.
    
    Args:
        info_type: Type of info - 'all', 'cpu', 'memory', 'disk', 'battery', 'network', 'uptime'
    """
    try:
        import psutil
    except ImportError:
        return "❌ psutil not installed. pip install psutil"

    info_type = (info_type or "all").lower()
    parts = []

    if info_type in ("all", "cpu"):
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        freq_str = f"{cpu_freq.current:.0f}MHz" if cpu_freq else "N/A"
        parts.append(f"🖥️  CPU: {cpu_percent}% ({cpu_count} cores @ {freq_str})")

    if info_type in ("all", "memory"):
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        parts.append(
            f"🧠 RAM: {mem.percent}% used "
            f"({_format_bytes(mem.used)}/{_format_bytes(mem.total)}) | "
            f"Swap: {swap.percent}% ({_format_bytes(swap.used)}/{_format_bytes(swap.total)})"
        )

    if info_type in ("all", "disk"):
        partitions = psutil.disk_partitions()
        for p in partitions:
            try:
                usage = psutil.disk_usage(p.mountpoint)
                parts.append(
                    f"💾 Disk {p.mountpoint}: {usage.percent}% used "
                    f"({_format_bytes(usage.used)}/{_format_bytes(usage.total)}) "
                    f"[{p.fstype}]"
                )
            except PermissionError:
                continue

    if info_type in ("all", "battery"):
        battery = psutil.sensors_battery()
        if battery:
            status = "🔌 Charging" if battery.power_plugged else "🔋 On Battery"
            time_left = ""
            if battery.secsleft > 0 and not battery.power_plugged:
                hours = battery.secsleft // 3600
                mins = (battery.secsleft % 3600) // 60
                time_left = f" ({hours}h {mins}m remaining)"
            parts.append(f"{status}: {battery.percent}%{time_left}")
        else:
            parts.append("🔌 No battery (desktop)")

    if info_type in ("all", "network"):
        net = psutil.net_io_counters()
        parts.append(
            f"🌐 Network: ↑ {_format_bytes(net.bytes_sent)} sent | "
            f"↓ {_format_bytes(net.bytes_recv)} received"
        )

    if info_type in ("all", "uptime"):
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        hours = int(uptime_seconds // 3600)
        mins = int((uptime_seconds % 3600) // 60)
        parts.append(f"⏱️  Uptime: {hours}h {mins}m")

    if info_type == "all":
        parts.insert(0, f"🖥️  {platform.node()} | {platform.system()} {platform.release()}")

    return "\n".join(parts) if parts else f"❌ Unknown info type: {info_type}"


def _format_bytes(bytes_val: int) -> str:
    """Format bytes in human-readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f}PB"
