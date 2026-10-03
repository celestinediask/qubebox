"""Disk operations for QubesOS-style root and private overlay disks."""

import os
import subprocess
from pathlib import Path
from typing import Optional

from qubebox.core.detector import SystemDetector


class DiskManager:
    @staticmethod
    def _run_qemu_img(args: list) -> subprocess.CompletedProcess:
        caps = SystemDetector.detect()
        binary = str(caps.qemu_img_path or "qemu-img")
        env = os.environ.copy()
        runtime_lib = caps.qemu_system_path.parent.parent / "lib" if caps.qemu_system_path else None
        if runtime_lib and runtime_lib.exists():
            env["LD_LIBRARY_PATH"] = f"{runtime_lib}:{env.get('LD_LIBRARY_PATH', '')}"

        return subprocess.run([binary] + args, capture_output=True, text=True, env=env, check=True)

    @classmethod
    def create_disk(cls, path: Path, size_gb: int, fmt: str = "qcow2") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        cls._run_qemu_img(["create", "-f", fmt, str(path), f"{size_gb}G"])

    @classmethod
    def create_overlay_disk(cls, backing_file: Path, overlay_file: Path) -> None:
        """Creates a copy-on-write overlay backed by an immutable root disk."""
        overlay_file.parent.mkdir(parents=True, exist_ok=True)
        # Using relative or absolute backing file
        cls._run_qemu_img([
            "create",
            "-f", "qcow2",
            "-F", "qcow2",
            "-b", str(backing_file.resolve()),
            str(overlay_file)
        ])
