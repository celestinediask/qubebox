"""Seamless Application Launcher with rootless sandboxing and QubesOS-style security isolation."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set

from qubebox.core.constants import (
    NET_MODE_NONE,
    NET_MODE_RESTRICTED,
    VM_TYPE_APPVM,
    VM_TYPE_DISPVM,
    VM_TYPE_STANDALONEVM,
    VM_TYPE_TEMPLATEVM,
)
from qubebox.core.process import VMProcessManager
from qubebox.core.vm import VMConfig, VMManager


class SeamlessAppLauncher:
    """Launches GUI applications in an isolated secure sandbox with colored seamless frames."""

    _app_processes: Dict[str, List[subprocess.Popen]] = {}  # vm_id -> [proc, ...]

    @classmethod
    def get_running_pids(cls, vm_id: str) -> List[int]:
        procs = cls._app_processes.get(vm_id, [])
        alive = []
        pids = []
        for p in procs:
            if p.poll() is None:
                alive.append(p)
                pids.append(p.pid)
        cls._app_processes[vm_id] = alive
        return pids

    @classmethod
    def has_running_apps(cls, vm_id: str) -> bool:
        return len(cls.get_running_pids(vm_id)) > 0

    @classmethod
    def terminate_apps(cls, vm_id: str, force: bool = False):
        import signal
        procs = cls._app_processes.get(vm_id, [])
        sig = signal.SIGKILL if force else signal.SIGTERM
        for p in procs:
            if p.poll() is None:
                try:
                    os.killpg(p.pid, sig)
                except Exception:
                    try:
                        if force:
                            p.kill()
                        else:
                            p.terminate()
                    except Exception:
                        pass
        cls._app_processes[vm_id] = []

    @classmethod
    def launch(
        cls,
        vm: VMConfig,
        vm_mgr: VMManager,
        command: str,
        app_name: str = ""
    ) -> subprocess.Popen:
        vm_dir = vm_mgr.get_vm_dir(vm.id)
        vm_dir.mkdir(parents=True, exist_ok=True)

        # Storage Isolation
        private_dir = vm_dir / "private"
        private_dir.mkdir(parents=True, exist_ok=True)

        # Build bubblewrap sandbox arguments
        bwrap = shutil.which("bwrap")
        if not bwrap:
            raise RuntimeError("bwrap (bubblewrap) is required for seamless isolation.")

        bwrap_cmd: List[str] = [
            bwrap,
            "--die-with-parent",
            "--ro-bind", "/", "/",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--tmpfs", "/run/user/1000",
            "--bind", "/tmp/.X11-unix", "/tmp/.X11-unix",
        ]

        # Bind Xauthority if present
        xauth = os.environ.get("XAUTHORITY", str(Path.home() / ".Xauthority"))
        if Path(xauth).exists():
            bwrap_cmd += ["--bind", xauth, xauth]

        # Storage mapping according to Qubes OS type
        if vm.vm_type == VM_TYPE_DISPVM or vm.is_disposable_instance:
            # Ephemeral user storage
            bwrap_cmd += ["--tmpfs", "/home/user"]
        else:
            # Persistent private storage per AppVM / TemplateVM
            bwrap_cmd += ["--bind", str(private_dir), "/home/user"]

        # Network Isolation
        if vm.network == NET_MODE_NONE:
            bwrap_cmd += ["--unshare-net"]

        # Hostname & IPC Isolation
        bwrap_cmd += [
            "--unshare-uts",
            "--hostname", f"{vm.name}-qube",
            "--unshare-ipc",
        ]

        # Environment configuration
        disp = os.environ.get("DISPLAY", ":0.0")
        bwrap_cmd += [
            "--setenv", "DISPLAY", disp,
            "--setenv", "XAUTHORITY", xauth,
            "--setenv", "HOME", "/home/user",
            "--setenv", "USER", "user",
            "--setenv", "QUBES_VM_NAME", vm.name,
            "--setenv", "QUBES_LABEL", vm.color,
            "--setenv", "QUBES_COLOR_HEX", vm.get_color_hex(),
        ]

        # App execution command
        dbus_session = shutil.which("dbus-run-session")
        if dbus_session:
            bwrap_cmd += [dbus_session, "--"]

        # Customize app arguments to enforce distinct window title and prevent daemon reuse
        if command == "thunar":
            app_args = ["thunar", "--window", "/home/user"]
        elif command == "xfce4-terminal":
            app_args = ["xfce4-terminal", "--disable-server", f"--title=[{vm.name}] Terminal", "--working-directory=/home/user"]
        elif command in ("firefox", "firefox-esr"):
            app_args = [command, "--no-remote", "--new-instance"]
        elif command == "xfce4-settings-manager":
            app_args = ["xfce4-settings-manager"]
        else:
            import shlex
            app_args = shlex.split(command)

        bwrap_cmd += app_args

        # Launch process
        log_file = open(vm_dir / "app.log", "a", encoding="utf-8")
        proc = subprocess.Popen(
            bwrap_cmd,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=log_file,
            cwd=str(vm_dir),
            start_new_session=True,
        )

        if vm.id not in cls._app_processes:
            cls._app_processes[vm.id] = []
        cls._app_processes[vm.id].append(proc)

        # Update running state
        VMProcessManager.set_status(vm.id, "running")

        return proc
