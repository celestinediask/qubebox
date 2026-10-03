"""Hardware and Environment Detector for rootless QEMU runtime."""

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from qubebox.core.constants import RUNTIME_DIR


@dataclass
class SystemCapabilities:
    qemu_system_path: Optional[Path] = None
    qemu_img_path: Optional[Path] = None
    kvm_available: bool = False
    seabios_path: Optional[Path] = None
    ovmf_code_path: Optional[Path] = None
    ovmf_vars_path: Optional[Path] = None
    display_backends: List[str] = field(default_factory=list)


class SystemDetector:
    _instance: Optional[SystemCapabilities] = None

    @classmethod
    def detect(cls, force_reload: bool = False) -> SystemCapabilities:
        if cls._instance is not None and not force_reload:
            return cls._instance

        caps = SystemCapabilities()

        # 1. Locate QEMU binaries
        # Check bundled runtime first
        bundled_system = RUNTIME_DIR / "bin" / "qemu-system-x86_64"
        bundled_img = RUNTIME_DIR / "bin" / "qemu-img"

        if bundled_system.is_file() and os.access(bundled_system, os.X_OK):
            caps.qemu_system_path = bundled_system
        else:
            sys_qemu = shutil.which("qemu-system-x86_64")
            if sys_qemu:
                caps.qemu_system_path = Path(sys_qemu)

        if bundled_img.is_file() and os.access(bundled_img, os.X_OK):
            caps.qemu_img_path = bundled_img
        else:
            sys_img = shutil.which("qemu-img")
            if sys_img:
                caps.qemu_img_path = Path(sys_img)

        # 2. Check KVM Acceleration
        kvm_dev = Path("/dev/kvm")
        if kvm_dev.exists() and os.access(kvm_dev, os.R_OK | os.W_OK):
            caps.kvm_available = True
        else:
            caps.kvm_available = False

        # 3. Locate Firmware (SeaBIOS & OVMF)
        seabios_candidates = [
            RUNTIME_DIR / "share" / "seabios" / "bios.bin",
            RUNTIME_DIR / "share" / "qemu" / "bios.bin",
            Path("/usr/share/seabios/bios.bin"),
            Path("/usr/share/qemu/bios.bin"),
        ]
        for c in seabios_candidates:
            if c.is_file():
                caps.seabios_path = c.parent
                break

        ovmf_code_candidates = [
            RUNTIME_DIR / "share" / "OVMF" / "OVMF_CODE_4M.fd",
            RUNTIME_DIR / "share" / "ovmf" / "OVMF_CODE_4M.fd",
            RUNTIME_DIR / "share" / "qemu" / "OVMF_CODE_4M.fd",
            Path("/usr/share/OVMF/OVMF_CODE_4M.fd"),
            Path("/usr/share/OVMF/OVMF_CODE.fd"),
        ]
        for c in ovmf_code_candidates:
            if c.is_file():
                caps.ovmf_code_path = c
                break

        ovmf_vars_candidates = [
            RUNTIME_DIR / "share" / "OVMF" / "OVMF_VARS_4M.fd",
            RUNTIME_DIR / "share" / "ovmf" / "OVMF_VARS_4M.fd",
            RUNTIME_DIR / "share" / "qemu" / "OVMF_VARS_4M.fd",
            Path("/usr/share/OVMF/OVMF_VARS_4M.fd"),
            Path("/usr/share/OVMF/OVMF_VARS.fd"),
        ]
        for c in ovmf_vars_candidates:
            if c.is_file():
                caps.ovmf_vars_path = c
                break

        # 4. Display backends supported
        caps.display_backends = ["gtk", "none", "sdl"]

        cls._instance = caps
        return caps
