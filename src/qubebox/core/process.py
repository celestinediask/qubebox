"""QEMU Process Runner with QMP integration, rootless networking, and seamless support."""

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from qubebox.core.constants import (
    NET_MODE_DEFAULT,
    NET_MODE_NONE,
    NET_MODE_RESTRICTED,
    VM_TYPE_APPVM,
    VM_TYPE_DISPVM,
    VM_TYPE_STANDALONEVM,
    VM_TYPE_TEMPLATEVM,
)
from qubebox.core.detector import SystemCapabilities, SystemDetector
from qubebox.core.disk import DiskManager
from qubebox.core.vm import VMConfig, VMManager


class VMProcessManager:
    """Manages running VM instances, QMP sockets, and process lifecycles."""

    _active_processes: Dict[str, subprocess.Popen] = {}

    @classmethod
    def is_running(cls, vm_id: str) -> bool:
        proc = cls._active_processes.get(vm_id)
        if proc:
            if proc.poll() is None:
                return True
            else:
                del cls._active_processes[vm_id]
        return False

    @classmethod
    def get_pid(cls, vm_id: str) -> Optional[int]:
        proc = cls._active_processes.get(vm_id)
        if proc and proc.poll() is None:
            return proc.pid
        return None

    @classmethod
    def start_vm(
        cls,
        vm: VMConfig,
        vm_mgr: VMManager,
        headless: bool = True
    ) -> subprocess.Popen:
        if cls.is_running(vm.id):
            raise RuntimeError(f"VM '{vm.name}' is already running!")

        caps = SystemDetector.detect()
        if not caps.qemu_system_path:
            raise RuntimeError("qemu-system-x86_64 binary not found.")

        vm_dir = vm_mgr.get_vm_dir(vm.id)
        vm_dir.mkdir(parents=True, exist_ok=True)

        # Handle Template vs AppVM / DispVM storage architecture
        root_disk = vm_dir / "root.qcow2"
        private_disk = vm_dir / "private.qcow2"
        standalone_disk = vm_dir / "disk.qcow2"

        if vm.vm_type == VM_TYPE_STANDALONEVM:
            if not standalone_disk.exists():
                DiskManager.create_disk(standalone_disk, vm.storage_gb)
        elif vm.vm_type == VM_TYPE_TEMPLATEVM:
            if not root_disk.exists():
                DiskManager.create_disk(root_disk, vm.storage_gb)
        elif vm.vm_type in (VM_TYPE_APPVM, VM_TYPE_DISPVM):
            # Must find template
            tpl_vm = vm_mgr.get_vm(vm.template) or vm_mgr.find_by_name(vm.template)
            if not tpl_vm:
                # If no explicit template found, check if a default template exists
                templates = vm_mgr.get_templates()
                if templates:
                    tpl_vm = templates[0]

            if tpl_vm:
                tpl_dir = vm_mgr.get_vm_dir(tpl_vm.id)
                tpl_root = tpl_dir / "root.qcow2"
                if not tpl_root.exists():
                    # Check standalone disk fallback in template
                    if (tpl_dir / "disk.qcow2").exists():
                        tpl_root = tpl_dir / "disk.qcow2"

                if tpl_root.exists():
                    # For DispVM, recreate fresh root overlay every time
                    if vm.vm_type == VM_TYPE_DISPVM or not root_disk.exists():
                        if root_disk.exists():
                            root_disk.unlink()
                        DiskManager.create_overlay_disk(tpl_root, root_disk)
                    # For private user storage
                    if not private_disk.exists():
                        DiskManager.create_disk(private_disk, vm.storage_gb)

        # Build QEMU arguments
        args: List[str] = [str(caps.qemu_system_path)]

        # 1. Identity & Process Name (Crucial for X11 Window Title detection!)
        # QEMU GTK window title starts with or contains the -name string
        window_title = f"QubeBox - {vm.name} [{vm.vm_type}]"
        args += ["-name", f"{window_title},process=qubebox-{vm.id}"]

        # 2. Machine & Acceleration
        args += ["-machine", "q35"]
        if caps.kvm_available:
            args += ["-accel", "kvm"]
            args += ["-cpu", "host"]
        else:
            args += ["-accel", "tcg"]
            args += ["-cpu", "max"]

        # 3. CPU & Memory
        cpus = max(1, vm.cpus)
        mem = max(256, vm.memory_mb)
        args += ["-smp", f"cpus={cpus},cores={cpus}"]
        args += ["-m", f"{mem}M"]
        args += ["-device", "virtio-balloon-pci"]

        # 4. Firmware (SeaBIOS)
        if caps.seabios_path:
            args += ["-L", str(caps.seabios_path)]
        share_qemu = caps.qemu_system_path.parent.parent / "share" / "qemu"
        if share_qemu.exists():
            args += ["-L", str(share_qemu)]

        # 5. Storage Attachments
        drive_idx = 0
        if vm.vm_type == VM_TYPE_STANDALONEVM:
            if standalone_disk.exists():
                args += ["-drive", f"file={standalone_disk},if=virtio,format=qcow2,cache=writeback,id=drive{drive_idx}"]
                drive_idx += 1
        elif vm.vm_type in (VM_TYPE_APPVM, VM_TYPE_DISPVM):
            if root_disk.exists():
                # Root is read-only or overlay
                args += ["-drive", f"file={root_disk},if=virtio,format=qcow2,cache=writeback,id=drive{drive_idx}"]
                drive_idx += 1
            if private_disk.exists() and vm.vm_type == VM_TYPE_APPVM:
                args += ["-drive", f"file={private_disk},if=virtio,format=qcow2,cache=writeback,id=drive{drive_idx}"]
                drive_idx += 1
        elif vm.vm_type == VM_TYPE_TEMPLATEVM:
            if root_disk.exists():
                args += ["-drive", f"file={root_disk},if=virtio,format=qcow2,cache=writeback,id=drive{drive_idx}"]
                drive_idx += 1

        # 6. CD-ROM / Boot ISO
        if vm.iso_path and Path(vm.iso_path).exists():
            args += ["-cdrom", str(Path(vm.iso_path).resolve())]
            args += ["-boot", "menu=on,order=dc"]
        else:
            args += ["-boot", "menu=on,order=c"]

        # 7. Network Isolation (Qubes-like security)
        if vm.network == NET_MODE_NONE:
            args += ["-net", "none"]
        elif vm.network == NET_MODE_RESTRICTED:
            # User mode with restricted mode (no external DNS/outbound ping)
            args += ["-netdev", f"user,id=net0,restrict=on", "-device", "virtio-net-pci,netdev=net0"]
        else:
            # Standard rootless user-mode NAT
            args += ["-netdev", f"user,id=net0", "-device", "virtio-net-pci,netdev=net0"]

        # 8. Display & GUI
        if headless:
            args += ["-display", "none"]
        else:
            # GTK display with zoom and clean interface
            args += ["-display", "gtk,gl=off,show-menubar=on,grab-on-hover=off"]
            args += ["-vga", "virtio"]

        # 9. Audio & Peripherals
        args += ["-audiodev", "none,id=snd0"]
        args += ["-device", "intel-hda", "-device", "hda-duplex,audiodev=snd0"]
        args += ["-device", "nec-usb-xhci,id=xhci"]
        args += ["-device", "usb-tablet,bus=xhci.0"]

        # 10. QMP Management Socket
        qmp_sock = vm_dir / "qmp.sock"
        if qmp_sock.exists():
            qmp_sock.unlink()
        args += ["-qmp", f"unix:{qmp_sock},server,nowait"]

        # 11. Extra custom arguments
        if vm.extra_qemu_args:
            import shlex
            args += shlex.split(vm.extra_qemu_args)

        # Environment configuration
        env = os.environ.copy()
        runtime_lib = caps.qemu_system_path.parent.parent / "lib"
        if runtime_lib.exists():
            env["LD_LIBRARY_PATH"] = f"{runtime_lib}:{env.get('LD_LIBRARY_PATH', '')}"
            env["QEMU_MODULE_DIR"] = str(runtime_lib / "qemu")

        log_file = open(vm_dir / "vm.log", "w", encoding="utf-8")

        proc = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(vm_dir),
            env=env,
            start_new_session=True,
        )

        cls._active_processes[vm.id] = proc
        return proc

    _vm_status: Dict[str, str] = {}  # "stopped", "running", "paused", "restarting", "error"

    @classmethod
    def get_status(cls, vm_id: str) -> str:
        # Check if recorded state is restarting or paused
        if cls._vm_status.get(vm_id) == "restarting":
            return "restarting"
        if cls._vm_status.get(vm_id) == "paused":
            return "paused"
        if cls.is_running(vm_id):
            return "running"
        try:
            from qubebox.core.seamless_launcher import SeamlessAppLauncher
            if SeamlessAppLauncher.has_running_apps(vm_id):
                return "running"
        except Exception:
            pass
        if cls._vm_status.get(vm_id) == "error":
            return "error"
        return "stopped"

    @classmethod
    def set_status(cls, vm_id: str, status: str):
        cls._vm_status[vm_id] = status

    @classmethod
    def toggle_pause_vm(cls, vm_id: str, vm_mgr: Optional[VMManager] = None) -> bool:
        if not cls.is_running(vm_id):
            return False
        vm_dir = vm_mgr.get_vm_dir(vm_id) if vm_mgr else (VMS_DIR / vm_id)
        qmp_sock = vm_dir / "qmp.sock"
        if not qmp_sock.exists():
            return False

        current_status = cls.get_status(vm_id)
        cmd = "cont" if current_status == "paused" else "stop"
        new_status = "running" if current_status == "paused" else "paused"

        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect(str(qmp_sock))
            s.recv(1024)
            s.sendall(b'{"execute": "qmp_capabilities"}\n')
            s.recv(1024)
            s.sendall(f'{{"execute": "{cmd}"}}\n'.encode("utf-8"))
            s.recv(1024)
            s.close()
            cls.set_status(vm_id, new_status)
            return True
        except Exception as e:
            print(f"Error toggling pause for VM {vm_id}: {e}")
            return False

    @classmethod
    def restart_vm(cls, vm: VMConfig, vm_mgr: VMManager, headless: bool = True):
        cls.set_status(vm.id, "restarting")
        cls.stop_vm(vm.id, force=False, vm_mgr=vm_mgr)
        # Give a small pause and restart
        try:
            cls.start_vm(vm, vm_mgr, headless=headless)
            cls.set_status(vm.id, "running")
        except Exception as e:
            cls.set_status(vm.id, "error")
            raise e

    @classmethod
    def stop_vm(cls, vm_id: str, force: bool = False, vm_mgr: Optional[VMManager] = None) -> bool:
        proc = cls._active_processes.get(vm_id)
        if not proc or proc.poll() is not None:
            if vm_id in cls._active_processes:
                del cls._active_processes[vm_id]
            if cls._vm_status.get(vm_id) != "restarting":
                cls._vm_status[vm_id] = "stopped"
            return False

        if not force:
            # Send graceful ACPI powerdown via QMP
            try:
                vm_dir = vm_mgr.get_vm_dir(vm_id) if vm_mgr else (VMS_DIR / vm_id)
                qmp_sock = vm_dir / "qmp.sock"
                if qmp_sock.exists():
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.settimeout(2.0)
                    s.connect(str(qmp_sock))
                    s.recv(1024)
                    s.sendall(b'{"execute": "qmp_capabilities"}\n')
                    s.recv(1024)
                    s.sendall(b'{"execute": "system_powerdown"}\n')
                    s.close()
                    # Wait up to 5 seconds
                    for _ in range(25):
                        if proc.poll() is not None:
                            break
                        time.sleep(0.2)
            except Exception:
                pass

        if proc.poll() is None:
            if force:
                proc.kill()
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()

        if vm_id in cls._active_processes:
            del cls._active_processes[vm_id]

        if cls._vm_status.get(vm_id) != "restarting":
            cls._vm_status[vm_id] = "stopped"

        # DispVM Cleanup
        if vm_mgr:
            vm = vm_mgr.get_vm(vm_id)
            if vm and (vm.vm_type == VM_TYPE_DISPVM or vm.is_disposable_instance):
                # Clean up ephemeral VM
                vm_mgr.delete_vm(vm_id)

        return True
