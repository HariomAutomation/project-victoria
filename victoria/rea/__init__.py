"""
Project Victoria - REA (Reverse Engineer Anything) Engine
Inspired by https://github.com/morluto/rea and next-gen AI system inspection.

Capable of reverse engineering:
- Websites & Web Applications (APIs, auth, tech stack, DOM, CSS tokens)
- Applications & Binaries (Electron/ASAR, Linux ELF binaries, running processes, Python bytecode, mobile packages)
- Databases (SQLite, PostgreSQL, MySQL, Redis, schemas, relationships, ERD)
- Devices & Networks (USB, PCI, Bluetooth, LAN devices, open ports, IoT services)
"""

from victoria.rea.teardown import ReverseEngineerEngine

__all__ = ["ReverseEngineerEngine"]
