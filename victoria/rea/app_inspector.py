"""
Victoria - REA Application Inspector
Reverse engineers applications and binaries:
- Electron / JavaScript / Node.js apps (ASAR archive inspection & unpacking, IPC channels, package.json)
- Native Linux ELF executables and shared libraries (.so) (symbols, dependencies, strings, security flags)
- Running desktop applications (PID/process introspection, open files, network sockets, memory maps)
- Python bytecode and packages
- Mobile APK packages (manifest, native libs, assets)
"""

import os
import json
import re
import struct
import subprocess
import shutil
import zipfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional
from rich.console import Console

console = Console()


@dataclass
class AppTeardownResult:
    target: str
    app_type: str  # "electron", "elf_binary", "running_process", "python", "apk", "generic"
    architecture: str = ""
    entry_point: str = ""
    dependencies: list[str] = field(default_factory=list)
    exported_functions: list[str] = field(default_factory=list)
    imported_functions: list[str] = field(default_factory=list)
    ipc_channels: list[dict[str, str]] = field(default_factory=list)
    extracted_strings: dict[str, list[str]] = field(default_factory=dict)
    open_network_sockets: list[str] = field(default_factory=list)
    open_files: list[str] = field(default_factory=list)
    security_features: dict[str, bool] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    reconstructed_skeleton: str = ""


class AppInspector:
    """
    Application & Binary Reverse Engineering Engine.
    """

    def __init__(self, output_dir: Optional[str] = None):
        from victoria.config import PROJECT_ROOT
        self.output_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "data" / "teardowns" / "extracted_apps"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def inspect(self, target: str) -> AppTeardownResult:
        """
        Reverse engineer an application target (file path or process name/PID).

        Args:
            target: Path to file (ELF binary, .so, .asar, .apk, .py) or PID / process name

        Returns:
            AppTeardownResult with recovered architecture, symbols, IPC, and strings.
        """
        console.print(f"[cyan]🔬 Reverse engineering application target: {target}[/cyan]")

        # 1. Check if target is a running process PID or name
        if target.isdigit() or (not os.path.exists(target) and self._find_pid_by_name(target)):
            pid = int(target) if target.isdigit() else self._find_pid_by_name(target)
            return self._inspect_running_process(pid, target)

        target_path = Path(target).resolve()
        if not target_path.exists():
            return AppTeardownResult(
                target=target,
                app_type="not_found",
                metadata={"error": f"Target not found: {target}"},
            )

        # 2. Check if target is an ASAR archive or directory containing app.asar
        if target_path.suffix == ".asar" or (target_path.is_dir() and (target_path / "resources" / "app.asar").exists()):
            asar_path = target_path if target_path.suffix == ".asar" else target_path / "resources" / "app.asar"
            return self._inspect_electron_app(asar_path)

        # 3. Check if target is an APK or ZIP archive
        if target_path.suffix in [".apk", ".jar", ".zip"]:
            return self._inspect_archive_app(target_path)

        # 4. Check if target is a Python script / package
        if target_path.suffix in [".py", ".pyc"]:
            return self._inspect_python_app(target_path)

        # 5. Default: inspect as ELF native binary or shared object
        return self._inspect_elf_binary(target_path)

    # =========================================================================
    # 1. Electron / ASAR App Reverse Engineering
    # =========================================================================

    def _inspect_electron_app(self, asar_path: Path) -> AppTeardownResult:
        """Reverse engineer an Electron application ASAR archive."""
        console.print(f"[dim]📦 Unpacking Electron ASAR archive: {asar_path.name}...[/dim]")
        extract_dir = self.output_dir / f"asar_{asar_path.stem}"
        extract_dir.mkdir(parents=True, exist_ok=True)

        result = AppTeardownResult(
            target=str(asar_path),
            app_type="electron",
            metadata={"asar_path": str(asar_path), "extracted_to": str(extract_dir)},
        )

        # Extract using Python ASAR unpacker or npx asar fallback
        unpacked_ok = self._unpack_asar(asar_path, extract_dir)
        if not unpacked_ok:
            result.metadata["warning"] = "Could not unpack ASAR completely."

        # Parse package.json
        pkg_json = extract_dir / "package.json"
        if pkg_json.exists():
            try:
                with open(pkg_json, "r", encoding="utf-8") as f:
                    pkg_data = json.load(f)
                    result.metadata["package_json"] = {
                        "name": pkg_data.get("name"),
                        "version": pkg_data.get("version"),
                        "main": pkg_data.get("main"),
                        "description": pkg_data.get("description"),
                    }
                    result.entry_point = pkg_data.get("main", "index.js")
                    result.dependencies = list(pkg_data.get("dependencies", {}).keys())
            except Exception as e:
                result.metadata["package_json_error"] = str(e)

        # Scan all JS files in unpacked directory for IPC channels and APIs
        ipc_channels = []
        api_endpoints = []

        for root, _, files in os.walk(extract_dir):
            for file in files:
                if file.endswith((".js", ".ts", ".json")):
                    filepath = Path(root) / file
                    try:
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                            # IPC send / invoke
                            for m in re.finditer(r'ipcRenderer\.(?:send|invoke)\(["\']([^"\']+)["\']', content):
                                ipc_channels.append({"channel": m.group(1), "direction": "renderer->main", "file": file})

                            # IPC handle / on
                            for m in re.finditer(r'ipcMain\.(?:on|handle)\(["\']([^"\']+)["\']', content):
                                ipc_channels.append({"channel": m.group(1), "direction": "main->handler", "file": file})

                            # API URLs
                            for m in re.finditer(r'https?://[a-zA-Z0-9_\-\.:/]+', content):
                                url = m.group(0)
                                if "localhost" not in url and "w3.org" not in url and url not in api_endpoints:
                                    api_endpoints.append(url)
                    except Exception:
                        continue

        # Deduplicate IPC
        seen_ipc = set()
        deduped_ipc = []
        for item in ipc_channels:
            key = (item["channel"], item["direction"])
            if key not in seen_ipc:
                seen_ipc.add(key)
                deduped_ipc.append(item)

        result.ipc_channels = deduped_ipc
        result.extracted_strings["api_urls"] = api_endpoints[:20]

        # Generate reconstructed skeleton
        result.reconstructed_skeleton = self._generate_electron_skeleton(result)
        return result

    def _unpack_asar(self, asar_path: Path, output_dir: Path) -> bool:
        """
        Unpack Electron ASAR file using pure Python implementation with npx fallback.
        """
        # Try pure python ASAR header parsing
        try:
            with open(asar_path, "rb") as f:
                header_size_bytes = f.read(16)
                if len(header_size_bytes) == 16:
                    # Pickle header: 4 bytes size, 4 bytes payload size, 4 bytes padding, 4 bytes json len
                    json_len = struct.unpack("<I", header_size_bytes[12:16])[0]
                    header_json_bytes = f.read(json_len)
                    header = json.loads(header_json_bytes.decode("utf-8"))

                    base_offset = 16 + json_len

                    def extract_tree(tree: dict, current_path: Path):
                        if "files" in tree:
                            for name, info in tree["files"].items():
                                child_path = current_path / name
                                if "files" in info:
                                    child_path.mkdir(parents=True, exist_ok=True)
                                    extract_tree(info, child_path)
                                elif "size" in info and "offset" in info:
                                    offset = int(info["offset"])
                                    size = int(info["size"])
                                    f.seek(base_offset + offset)
                                    data = f.read(size)
                                    child_path.parent.mkdir(parents=True, exist_ok=True)
                                    with open(child_path, "wb") as out_f:
                                        out_f.write(data)

                    extract_tree(header, output_dir)
                    return True
        except Exception as e:
            console.print(f"[dim]Pure Python ASAR parsing fallback: {e}[/dim]")

        # Fallback to npx asar extract
        if shutil.which("npx"):
            try:
                res = subprocess.run(
                    ["npx", "-y", "@electron/asar", "extract", str(asar_path), str(output_dir)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return res.returncode == 0
            except Exception:
                pass

        return False

    def _generate_electron_skeleton(self, result: AppTeardownResult) -> str:
        lines = [
            f"// Reconstructed Electron App Skeleton for {Path(result.target).stem}",
            "// Auto-generated by Project Victoria REA Engine\n",
            "const { app, BrowserWindow, ipcMain } = require('electron');\n",
            "function createWindow() {",
            "    const win = new BrowserWindow({",
            "        width: 1200, height: 800,",
            "        webPreferences: { nodeIntegration: true, contextIsolation: false }",
            "    });",
            f"    win.loadFile('{result.entry_point or 'index.html'}');",
            "}\n",
            "// Registered IPC Handlers recovered from ASAR teardown:",
        ]
        for ipc in result.ipc_channels:
            if "main" in ipc["direction"]:
                lines.append(f"ipcMain.handle('{ipc['channel']}', async (event, args) => {{")
                lines.append(f"    console.log('IPC channel [{ipc['channel']}] received:', args);")
                lines.append("    return { status: 'ok', channel: '" + ipc['channel'] + "' };")
                lines.append("});\n")

        lines.append("app.whenReady().then(createWindow);")
        return "\n".join(lines)

    # =========================================================================
    # 2. Native Linux ELF Binary Reverse Engineering
    # =========================================================================

    def _inspect_elf_binary(self, binary_path: Path) -> AppTeardownResult:
        """Reverse engineer a native Linux ELF executable or shared library."""
        result = AppTeardownResult(
            target=str(binary_path),
            app_type="elf_binary",
        )

        # 1. Readelf header & architecture
        if shutil.which("readelf"):
            try:
                res = subprocess.run(["readelf", "-h", str(binary_path)], capture_output=True, text=True, timeout=5)
                for line in res.stdout.splitlines():
                    if "Class:" in line:
                        result.metadata["class"] = line.split("Class:")[1].strip()
                    elif "Machine:" in line:
                        result.architecture = line.split("Machine:")[1].strip()
                    elif "Entry point address:" in line:
                        result.entry_point = line.split("Entry point address:")[1].strip()
            except Exception:
                pass

        # 2. Shared Libraries (ldd)
        if shutil.which("ldd"):
            try:
                res = subprocess.run(["ldd", str(binary_path)], capture_output=True, text=True, timeout=5)
                libs = []
                for line in res.stdout.splitlines():
                    parts = line.strip().split("=>")
                    lib_name = parts[0].strip().split()[0]
                    if lib_name and lib_name not in libs:
                        libs.append(lib_name)
                result.dependencies = libs
            except Exception:
                pass

        # 3. Dynamic Symbols & Exported/Imported Functions (nm)
        if shutil.which("nm"):
            try:
                res = subprocess.run(
                    ["nm", "-D", "--demangle", str(binary_path)],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                for line in res.stdout.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        sym_type = parts[1]
                        sym_name = " ".join(parts[2:])
                        if sym_type in ["T", "W"]:  # Exported / Defined Text symbol
                            if len(result.exported_functions) < 50:
                                result.exported_functions.append(sym_name)
                        elif sym_type == "U":  # Undefined / Imported symbol
                            if len(result.imported_functions) < 50:
                                result.imported_functions.append(sym_name)
            except Exception:
                pass

        # 4. Strings Extraction & Classification
        if shutil.which("strings"):
            try:
                res = subprocess.run(["strings", "-a", "-n", "6", str(binary_path)], capture_output=True, text=True, timeout=8)
                all_strings = res.stdout.splitlines()

                urls = [s for s in all_strings if re.match(r'^https?://', s)][:20]
                paths = [s for s in all_strings if re.match(r'^/(?:etc|usr|var|home|opt|tmp)/', s)][:25]
                sqls = [s for s in all_strings if re.match(r'^(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP)\b', s, re.IGNORECASE)][:15]

                result.extracted_strings = {
                    "urls": urls,
                    "file_paths": paths,
                    "sql_queries": sqls,
                }
            except Exception:
                pass

        # 5. Security Mitigations (checksec style)
        if shutil.which("readelf"):
            try:
                res_l = subprocess.run(["readelf", "-l", str(binary_path)], capture_output=True, text=True, timeout=5)
                result.security_features["NX"] = "GNU_STACK" in res_l.stdout and "RWE" not in res_l.stdout
                result.security_features["PIE"] = "DYN (Position-Independent Executable" in res.stdout if 'res' in locals() else True
            except Exception:
                pass

        return result

    # =========================================================================
    # 3. Live Running Process Reverse Engineering
    # =========================================================================

    def _find_pid_by_name(self, name: str) -> Optional[int]:
        try:
            res = subprocess.run(["pgrep", "-f", "-o", name], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                return int(res.stdout.strip().split()[0])
        except Exception:
            pass
        return None

    def _inspect_running_process(self, pid: int, target_name: str) -> AppTeardownResult:
        """Inspect a currently running process using /proc and system tools."""
        proc_path = Path(f"/proc/{pid}")
        result = AppTeardownResult(
            target=f"{target_name} (PID: {pid})",
            app_type="running_process",
        )

        if not proc_path.exists():
            result.metadata["error"] = f"Process {pid} is not running."
            return result

        # Read command line arguments
        try:
            cmdline_bytes = (proc_path / "cmdline").read_bytes()
            cmdline = " ".join([part.decode("utf-8", "ignore") for part in cmdline_bytes.split(b"\x00") if part])
            result.metadata["cmdline"] = cmdline
        except Exception:
            pass

        # Read cwd and exe
        try:
            result.metadata["cwd"] = os.readlink(str(proc_path / "cwd"))
            result.entry_point = os.readlink(str(proc_path / "exe"))
        except Exception:
            pass

        # Open file descriptors
        try:
            fd_dir = proc_path / "fd"
            open_files = []
            if fd_dir.exists():
                for fd in list(fd_dir.iterdir())[:30]:
                    try:
                        target = os.readlink(str(fd))
                        if target.startswith("/"):
                            open_files.append(target)
                    except Exception:
                        pass
            result.open_files = list(dict.fromkeys(open_files))
        except Exception:
            pass

        # Open network connections / sockets via ss
        if shutil.which("ss"):
            try:
                res = subprocess.run(["ss", "-tulpn", f"pid = {pid}"], capture_output=True, text=True, timeout=5)
                lines = [l.strip() for l in res.stdout.splitlines()[1:] if l.strip()]
                result.open_network_sockets = lines
            except Exception:
                pass

        # Loaded shared libraries from maps
        try:
            maps_content = (proc_path / "maps").read_text(errors="ignore")
            loaded_libs = set()
            for line in maps_content.splitlines():
                parts = line.split()
                if len(parts) >= 6 and parts[5].endswith(".so"):
                    loaded_libs.add(os.path.basename(parts[5]))
            result.dependencies = sorted(list(loaded_libs))[:30]
        except Exception:
            pass

        return result

    # =========================================================================
    # 4. Mobile & Archive Inspection (APK, JAR, ZIP)
    # =========================================================================

    def _inspect_archive_app(self, archive_path: Path) -> AppTeardownResult:
        result = AppTeardownResult(
            target=str(archive_path),
            app_type="apk" if archive_path.suffix == ".apk" else "archive",
        )

        try:
            with zipfile.ZipFile(archive_path, "r") as z:
                namelist = z.namelist()
                native_libs = [n for n in namelist if n.startswith("lib/") and n.endswith(".so")]
                assets = [n for n in namelist if n.startswith("assets/")][:20]

                result.dependencies = native_libs[:30]
                result.metadata["total_files"] = len(namelist)
                result.metadata["assets"] = assets
                result.metadata["has_manifest"] = "AndroidManifest.xml" in namelist
        except Exception as e:
            result.metadata["error"] = str(e)

        return result

    # =========================================================================
    # 5. Python Application Inspection
    # =========================================================================

    def _inspect_python_app(self, py_path: Path) -> AppTeardownResult:
        import ast
        result = AppTeardownResult(
            target=str(py_path),
            app_type="python",
        )

        try:
            content = py_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(content)

            imports = []
            functions = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append(node.name)

            result.dependencies = list(dict.fromkeys(imports))
            result.exported_functions = functions
        except Exception as e:
            result.metadata["ast_error"] = str(e)

        return result
