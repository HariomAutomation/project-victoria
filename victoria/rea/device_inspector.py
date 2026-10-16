"""
Victoria - REA Device & Network Inspector
Reverse engineers devices, hardware peripherals, network interfaces, and IoT targets:
- USB devices (vendor/product ID, descriptors, device classes)
- PCI buses, GPUs, storage devices, and kernel drivers
- Bluetooth peripherals and BLE devices
- Local network devices (ARP discovery, LAN hosts, IoT cameras, smart TVs)
- Open ports, listening sockets, and service banner grabbing
"""

import re
import socket
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import Any
from rich.console import Console

console = Console()


@dataclass
class DeviceTeardownResult:
    target: str
    device_type: str  # "usb", "pci", "bluetooth", "network_host", "lan_scan", "system_hardware"
    devices_found: list[dict[str, Any]] = field(default_factory=list)
    open_ports: list[dict[str, Any]] = field(default_factory=list)
    banners_captured: dict[str, str] = field(default_factory=dict)
    interfaces: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    reconstructed_profile: str = ""


class DeviceInspector:
    """
    Device, Hardware, and Network Reverse Engineering Engine.
    """

    def inspect(self, target: str = "all") -> DeviceTeardownResult:
        """
        Reverse engineer a device, hardware component, IP address, or local environment.

        Args:
            target: "all", "usb", "pci", "bluetooth", "network", or specific IP/hostname (e.g. "192.168.1.1")

        Returns:
            DeviceTeardownResult containing hardware profiles, open ports, and banners.
        """
        console.print(f"[cyan]🔌 Reverse engineering device/hardware target: {target}[/cyan]")
        target_lower = target.lower().strip()

        # Check if target is an IP address or hostname
        if re.match(r'^(?:\d{1,3}\.){3}\d{1,3}$', target_lower) or target_lower.startswith(("http://", "https://", "ip:")):
            clean_ip = re.sub(r'^(?:https?://|ip:)', '', target_lower).split('/')[0].split(':')[0]
            return self._inspect_network_host(clean_ip)

        if "usb" in target_lower:
            return self._inspect_usb()
        elif "pci" in target_lower or "gpu" in target_lower:
            return self._inspect_pci()
        elif "bt" in target_lower or "bluetooth" in target_lower:
            return self._inspect_bluetooth()
        elif "net" in target_lower or "lan" in target_lower or "wifi" in target_lower:
            return self._inspect_lan()
        else:
            # Full comprehensive device & hardware scan
            return self._inspect_all()

    # =========================================================================
    # 1. USB Reverse Engineering
    # =========================================================================

    def _inspect_usb(self) -> DeviceTeardownResult:
        result = DeviceTeardownResult(target="USB Bus", device_type="usb")

        if shutil.which("lsusb"):
            try:
                res = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
                devices = []
                for line in res.stdout.splitlines():
                    match = re.match(r'Bus\s+(\d+)\s+Device\s+(\d+):\s+ID\s+([0-9a-fA-F:]+)\s+(.*)', line)
                    if match:
                        devices.append({
                            "bus": match.group(1),
                            "device": match.group(2),
                            "id": match.group(3),
                            "description": match.group(4).strip(),
                        })
                    else:
                        devices.append({"raw": line.strip()})
                result.devices_found = devices
            except Exception as e:
                result.metadata["error"] = str(e)
        else:
            result.metadata["error"] = "lsusb utility not found."

        result.reconstructed_profile = f"Found {len(result.devices_found)} connected USB devices."
        return result

    # =========================================================================
    # 2. PCI & Hardware Reverse Engineering
    # =========================================================================

    def _inspect_pci(self) -> DeviceTeardownResult:
        result = DeviceTeardownResult(target="PCI Bus", device_type="pci")

        if shutil.which("lspci"):
            try:
                res = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
                devices = []
                for line in res.stdout.splitlines():
                    parts = line.strip().split(" ", 1)
                    if len(parts) == 2:
                        devices.append({
                            "slot": parts[0],
                            "device": parts[1],
                        })
                result.devices_found = devices
            except Exception as e:
                result.metadata["error"] = str(e)
        return result

    # =========================================================================
    # 3. Bluetooth Reverse Engineering
    # =========================================================================

    def _inspect_bluetooth(self) -> DeviceTeardownResult:
        result = DeviceTeardownResult(target="Bluetooth", device_type="bluetooth")

        if shutil.which("bluetoothctl"):
            try:
                res = subprocess.run(["bluetoothctl", "devices"], capture_output=True, text=True, timeout=5)
                devices = []
                for line in res.stdout.splitlines():
                    match = re.match(r'Device\s+([0-9A-Fa-f:]+)\s+(.*)', line)
                    if match:
                        devices.append({
                            "mac": match.group(1),
                            "name": match.group(2).strip(),
                        })
                result.devices_found = devices
            except Exception as e:
                result.metadata["error"] = str(e)
        return result

    # =========================================================================
    # 4. Network Host / IoT Device Reverse Engineering
    # =========================================================================

    def _inspect_network_host(self, host: str) -> DeviceTeardownResult:
        """
        Reverse engineer a remote device/host (IP address, IoT device, router, camera).
        Scans common ports and grabs service banners.
        """
        result = DeviceTeardownResult(target=host, device_type="network_host")

        # Standard IoT and server ports to probe
        ports_to_probe = [
            (21, "FTP"),
            (22, "SSH"),
            (23, "Telnet"),
            (53, "DNS"),
            (80, "HTTP"),
            (443, "HTTPS"),
            (554, "RTSP (Camera Stream)"),
            (1883, "MQTT (IoT Broker)"),
            (3000, "Node / Dev Server"),
            (3306, "MySQL"),
            (5432, "PostgreSQL"),
            (6379, "Redis"),
            (8000, "HTTP Alt"),
            (8080, "HTTP Proxy / Web Admin"),
            (8443, "HTTPS Alt"),
        ]

        console.print(f"[dim]📡 Scanning open ports & banners on {host}...[/dim]")
        for port, service in ports_to_probe:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.6)
                code = s.connect_ex((host, port))
                if code == 0:
                    banner = ""
                    # Probe banner
                    try:
                        if port in [80, 8080, 8000]:
                            s.sendall(b"HEAD / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n")
                        banner_data = s.recv(512)
                        banner = banner_data.decode("utf-8", "ignore").strip()
                    except Exception:
                        pass

                    result.open_ports.append({
                        "port": port,
                        "service": service,
                        "status": "open",
                        "banner": banner[:100] if banner else None,
                    })
                    if banner:
                        result.banners_captured[f"{port}/{service}"] = banner[:200]
                s.close()
            except Exception:
                continue

        result.reconstructed_profile = (
            f"Host {host} has {len(result.open_ports)} open ports: "
            + ", ".join([f"{p['port']} ({p['service']})" for p in result.open_ports])
        )
        return result

    # =========================================================================
    # 5. Local LAN & Listening Sockets Scan
    # =========================================================================

    def _inspect_lan(self) -> DeviceTeardownResult:
        result = DeviceTeardownResult(target="Local Network", device_type="lan_scan")

        # 1. Network Interfaces (ip addr)
        try:
            res_ip = subprocess.run(["ip", "-brief", "addr"], capture_output=True, text=True, timeout=5)
            for line in res_ip.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    result.interfaces.append({
                        "interface": parts[0],
                        "status": parts[1],
                        "address": parts[2],
                    })
        except Exception:
            pass

        # 2. Neighbors / ARP table (ip neigh)
        try:
            res_neigh = subprocess.run(["ip", "neigh"], capture_output=True, text=True, timeout=5)
            devices = []
            for line in res_neigh.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[1] == "dev":
                    devices.append({
                        "ip": parts[0],
                        "interface": parts[2],
                        "mac": parts[4] if len(parts) > 4 else "unknown",
                        "state": parts[-1],
                    })
            result.devices_found = devices
        except Exception:
            pass

        return result

    def _inspect_all(self) -> DeviceTeardownResult:
        """Combine USB, PCI, Bluetooth, and local listening ports."""
        result = DeviceTeardownResult(target="All System Devices & Hardware", device_type="system_hardware")

        usb_res = self._inspect_usb()
        pci_res = self._inspect_pci()
        bt_res = self._inspect_bluetooth()

        result.devices_found = [
            {"category": "USB", "count": len(usb_res.devices_found), "sample": usb_res.devices_found[:10]},
            {"category": "PCI", "count": len(pci_res.devices_found), "sample": pci_res.devices_found[:10]},
            {"category": "Bluetooth", "count": len(bt_res.devices_found), "sample": bt_res.devices_found[:10]},
        ]

        # Listening ports (ss -tulpn)
        if shutil.which("ss"):
            try:
                res_ss = subprocess.run(["ss", "-tulpn"], capture_output=True, text=True, timeout=5)
                lines = [l.strip() for l in res_ss.stdout.splitlines()[1:] if l.strip()][:25]
                result.metadata["local_listening_sockets"] = lines
            except Exception:
                pass

        return result
