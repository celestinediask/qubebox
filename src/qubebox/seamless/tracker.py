"""Seamless Window Manager: tracks running VM windows and dynamically anchors colored borders."""

import os
import time
from typing import Dict, List, Optional, Set, Tuple

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from qubebox.core.process import VMProcessManager
from qubebox.core.seamless_launcher import SeamlessAppLauncher
from qubebox.core.vm import VMConfig
from qubebox.seamless.overlay import BorderOverlayWindow
from qubebox.seamless.x11_bridge import X11Bridge


def get_pid_qube_name(pid: int) -> Optional[str]:
    curr = pid
    for _ in range(6):
        try:
            env_path = f"/proc/{curr}/environ"
            if os.path.exists(env_path):
                with open(env_path, "rb") as f:
                    for entry in f.read().split(b"\x00"):
                        if entry.startswith(b"QUBES_VM_NAME="):
                            return entry.split(b"=", 1)[1].decode("utf-8")
            stat_path = f"/proc/{curr}/stat"
            if not os.path.exists(stat_path):
                break
            with open(stat_path, "r") as f:
                ppid = int(f.read().split()[3])
            if ppid <= 1:
                break
            curr = ppid
        except Exception:
            break
    return None


def is_pid_descendant(pid: int, ancestor_pids: Set[int]) -> bool:
    if pid in ancestor_pids:
        return True
    curr = pid
    for _ in range(6):
        try:
            stat_path = f"/proc/{curr}/stat"
            if not os.path.exists(stat_path):
                break
            with open(stat_path, "r") as f:
                ppid = int(f.read().split()[3])
            if ppid in ancestor_pids:
                return True
            if ppid <= 1:
                break
            curr = ppid
        except Exception:
            break
    return False


class SeamlessTracker:
    """Monitors X11 windows corresponding to running VMs and attaches colored borders."""

    def __init__(self):
        self.bridge = X11Bridge()
        self.overlays: Dict[int, BorderOverlayWindow] = {}  # xid -> overlay
        self.window_vms: Dict[int, str] = {}  # xid -> vm_id
        self.vm_configs: Dict[str, VMConfig] = {}
        self._timer_id: Optional[int] = None

    def start(self):
        if self._timer_id is None:
            # Poll every 200ms for smooth window movement and resizing
            self._timer_id = GLib.timeout_add(200, self._tick)

    def stop(self):
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None
        for overlay in self.overlays.values():
            overlay.destroy()
        self.overlays.clear()
        self.window_vms.clear()
        self.bridge.close()

    def register_vm(self, vm: VMConfig):
        self.vm_configs[vm.id] = vm

    def unregister_vm(self, vm_id: str):
        if vm_id in self.vm_configs:
            del self.vm_configs[vm_id]
        # Remove any overlays for this VM
        for xid, v_id in list(self.window_vms.items()):
            if v_id == vm_id:
                if xid in self.overlays:
                    self.overlays[xid].destroy()
                    del self.overlays[xid]
                del self.window_vms[xid]

    def _tick(self) -> bool:
        if not self.bridge.is_available():
            return True

        client_windows = self.bridge.get_client_windows()
        client_windows_set = set(client_windows)

        # Clean up closed windows
        for xid in list(self.overlays.keys()):
            if xid not in client_windows_set:
                self.overlays[xid].destroy()
                del self.overlays[xid]
                if xid in self.window_vms:
                    del self.window_vms[xid]

        # Precompute geometries of all visible client windows in stacking order
        window_geoms = {}
        for cw in client_windows:
            g = self.bridge.get_full_window_geometry(cw) or self.bridge.get_window_geometry(cw)
            if g and g[2] > 20 and g[3] > 20:
                window_geoms[cw] = g

        # Scan running VMs
        for vm_id, vm in list(self.vm_configs.items()):
            if not vm.seamless_mode:
                continue

            # Gather target PIDs for this VM
            target_pids = set()
            qemu_pid = VMProcessManager.get_pid(vm_id)
            if qemu_pid:
                target_pids.add(qemu_pid)
            for apid in SeamlessAppLauncher.get_running_pids(vm_id):
                target_pids.add(apid)

            # Check all client windows to find matches for this VM
            for xid in client_windows:
                # Skip windows already owned by another VM
                if xid in self.window_vms and self.window_vms[xid] != vm_id:
                    continue

                w_pid = self.bridge.get_window_pid(xid)
                matched = False

                # 1. Match by QUBES_VM_NAME environment variable
                qube_env = get_pid_qube_name(w_pid) if w_pid else None
                if qube_env and (qube_env == vm.name or qube_env == vm.id):
                    matched = True
                # 2. Match by exact PID or descendant process PID
                elif w_pid and is_pid_descendant(w_pid, target_pids):
                    matched = True
                else:
                    # 3. Check title tags
                    title = self.bridge.get_window_title(xid)
                    if f"QubeBox - {vm.name}" in title or f"[{vm.name}]" in title:
                        matched = True

                if matched:
                    self.window_vms[xid] = vm_id
                    geom = window_geoms.get(xid)
                    if geom:
                        rx, ry, rw, rh = geom
                        if rw > 50 and rh > 50:
                            # Calculate all windows stacked above xid
                            idx = client_windows.index(xid) if xid in client_windows else -1
                            occluding_rects = []
                            if idx >= 0:
                                for above_xid in client_windows[idx + 1:]:
                                    if above_xid in window_geoms:
                                        occluding_rects.append(window_geoms[above_xid])

                            overlay = self.overlays.get(xid)
                            if not overlay:
                                overlay = BorderOverlayWindow(
                                    color_hex=vm.get_color_hex(),
                                    border_width=vm.border_width,
                                    title_label=f"[{vm.color.capitalize()}] {vm.name} ({vm.vm_type})"
                                )
                                overlay.show_all()
                                self.overlays[xid] = overlay

                            overlay.update_geometry(rx, ry, rw, rh, occluding_rects)
                        else:
                            if xid in self.overlays:
                                self.overlays[xid].hide()

        # Restack overlays in bottom-to-top order to eliminate any overlapping border lines
        for xid in client_windows:
            overlay = self.overlays.get(xid)
            if overlay:
                gdk_win = overlay.get_window()
                if gdk_win and hasattr(gdk_win, "get_xid"):
                    self.bridge.raise_window(gdk_win.get_xid())

        # Ensure active focused window overlay is always on top
        active_xid = self.bridge.get_active_window()
        if active_xid in self.overlays:
            act_win = self.overlays[active_xid].get_window()
            if act_win and hasattr(act_win, "get_xid"):
                self.bridge.raise_window(act_win.get_xid())

        # Update status for VMs whose apps have all closed
        for vm_id, vm in list(self.vm_configs.items()):
            if not VMProcessManager.is_running(vm_id) and not SeamlessAppLauncher.has_running_apps(vm_id):
                if VMProcessManager.get_status(vm_id) == "running":
                    VMProcessManager.set_status(vm_id, "stopped")

        return True
