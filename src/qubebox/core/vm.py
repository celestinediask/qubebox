"""Virtual Machine Data Model and Configuration."""

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from qubebox.core.constants import (
    COLOR_MAP,
    NET_MODE_DEFAULT,
    VM_TYPE_APPVM,
    VM_TYPE_DISPVM,
    VM_TYPE_STANDALONEVM,
    VM_TYPE_TEMPLATEVM,
    VMS_DIR,
)


@dataclass
class VMConfig:
    id: str
    name: str
    vm_type: str = VM_TYPE_APPVM  # AppVM, TemplateVM, StandaloneVM, DispVM
    color: str = "Red"            # Red, Orange, Yellow, Green, Blue, Purple, Gray, Black
    template: str = ""           # ID or name of template if AppVM or DispVM
    cpus: int = 1
    memory_mb: int = 512
    storage_gb: int = 2         # User private storage or standalone disk size
    network: str = NET_MODE_DEFAULT # default, none, isolated
    iso_path: str = ""           # Boot/Install ISO if applicable
    seamless_mode: bool = True   # Enable color-bordered seamless integration
    border_width: int = 4        # Width of colored border in pixels
    extra_qemu_args: str = ""    # Custom flags if needed
    created_at: str = ""
    is_disposable_instance: bool = False
    parent_dispvm_template: str = ""

    def get_color_hex(self) -> str:
        return COLOR_MAP.get(self.color, "#e74c3c")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VMConfig":
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


class VMManager:
    """Manages VM configurations and disk state on disk."""

    def __init__(self, base_dir: Path = VMS_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.vms: Dict[str, VMConfig] = {}
        self.load_all()

    def get_vm_dir(self, vm_id: str) -> Path:
        return self.base_dir / vm_id

    def get_vm_config_file(self, vm_id: str) -> Path:
        return self.get_vm_dir(vm_id) / "vm.json"

    def load_all(self) -> None:
        self.vms.clear()
        if not self.base_dir.exists():
            return
        for vm_folder in self.base_dir.iterdir():
            if vm_folder.is_dir():
                cfg_file = vm_folder / "vm.json"
                if cfg_file.is_file():
                    try:
                        with open(cfg_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            vm = VMConfig.from_dict(data)
                            self.vms[vm.id] = vm
                    except Exception as e:
                        print(f"Failed to load VM from {cfg_file}: {e}")

    def list_vms(self) -> List[VMConfig]:
        return list(self.vms.values())

    def get_templates(self) -> List[VMConfig]:
        return [vm for vm in self.vms.values() if vm.vm_type == VM_TYPE_TEMPLATEVM]

    def get_vm(self, vm_id: str) -> Optional[VMConfig]:
        return self.vms.get(vm_id)

    def find_by_name(self, name: str) -> Optional[VMConfig]:
        for vm in self.vms.values():
            if vm.name.lower() == name.lower():
                return vm
        return None

    def save_vm(self, vm: VMConfig) -> None:
        vm_dir = self.get_vm_dir(vm.id)
        vm_dir.mkdir(parents=True, exist_ok=True)
        with open(self.get_vm_config_file(vm.id), "w", encoding="utf-8") as f:
            json.dump(vm.to_dict(), f, indent=2)
        self.vms[vm.id] = vm

    def delete_vm(self, vm_id: str) -> None:
        import shutil
        if vm_id in self.vms:
            del self.vms[vm_id]
        vm_dir = self.get_vm_dir(vm_id)
        if vm_dir.exists():
            shutil.rmtree(vm_dir, ignore_errors=True)
