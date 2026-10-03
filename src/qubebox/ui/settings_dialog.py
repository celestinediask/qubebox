"""Application Settings Dialog with minimal clean options."""

import os
import shutil
from pathlib import Path
from typing import List, Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from qubebox.core.constants import APP_ROOT, VM_TYPE_TEMPLATEVM, VMS_DIR
from qubebox.core.process import VMProcessManager
from qubebox.core.seamless_launcher import SeamlessAppLauncher
from qubebox.core.vm import VMConfig, VMManager
from qubebox.ui.create_dialog import QubeConfigDialog, VMSettingsDialog


class AppSettingsDialog(Gtk.Dialog):
    """Ultra-minimal Settings Dialog providing straightforward clear options."""

    def __init__(self, parent: Gtk.Window, vm_mgr: VMManager):
        super().__init__(title="Settings", transient_for=parent, flags=0)
        self.set_modal(True)
        self.set_default_size(300, 210)
        self.set_resizable(False)
        self.get_style_context().add_class("settings-dialog")
        self.parent_window = parent
        self.vm_mgr = vm_mgr

        content = self.get_content_area()
        content.set_spacing(12)
        content.set_margin_start(20)
        content.set_margin_end(20)
        content.set_margin_top(16)
        content.set_margin_bottom(12)

        # Options Box
        vbox_options = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.pack_start(vbox_options, True, True, 0)

        self.chk_cache = Gtk.CheckButton(label="Clear cache")
        self.chk_logs = Gtk.CheckButton(label="Clear logs")
        self.chk_data = Gtk.CheckButton(label="Clear data")
        self.chk_templates = Gtk.CheckButton(label="Clear templates")

        vbox_options.pack_start(self.chk_cache, False, False, 0)
        vbox_options.pack_start(self.chk_logs, False, False, 0)
        vbox_options.pack_start(self.chk_data, False, False, 0)
        vbox_options.pack_start(self.chk_templates, False, False, 0)

        # Action bar with Clear button and feedback
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        self.btn_clear = Gtk.Button(label="Clear")
        self.btn_clear.get_style_context().add_class("btn-destructive")
        self.btn_clear.connect("clicked", self._on_clear_clicked)
        action_box.pack_start(self.btn_clear, False, False, 0)

        self.btn_close = Gtk.Button(label="Close")
        self.btn_close.connect("clicked", lambda b: self.response(Gtk.ResponseType.CLOSE))
        action_box.pack_end(self.btn_close, False, False, 0)

        content.pack_start(action_box, False, False, 0)

        self.lbl_feedback = Gtk.Label()
        self.lbl_feedback.set_xalign(0.0)
        content.pack_start(self.lbl_feedback, False, False, 0)

        self.show_all()

    def _on_clear_clicked(self, btn):
        clear_cache = self.chk_cache.get_active()
        clear_logs = self.chk_logs.get_active()
        clear_data = self.chk_data.get_active()
        clear_templates = self.chk_templates.get_active()

        if not any([clear_cache, clear_logs, clear_data, clear_templates]):
            self.lbl_feedback.set_markup("<span foreground='#8c8fa8'>Select an option to clear.</span>")
            return

        # Perform Selected Clear Actions
        done_items = []

        # 1. Clear cache
        if clear_cache:
            for p in APP_ROOT.rglob("__pycache__"):
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
            for f in APP_ROOT.rglob("*.pyc"):
                try:
                    f.unlink(missing_ok=True)
                except Exception:
                    pass
            done_items.append("cache")

        # 2. Clear logs
        if clear_logs:
            for f in APP_ROOT.glob("*.log"):
                try:
                    f.unlink(missing_ok=True)
                except Exception:
                    pass
            if VMS_DIR.exists():
                for f in VMS_DIR.rglob("*"):
                    if f.is_file() and (f.suffix == ".log" or f.name.endswith(".sock")):
                        try:
                            f.unlink(missing_ok=True)
                        except Exception:
                            pass
            done_items.append("logs")

        # 3. Clear data (User AppVMs, DispVMs, and private overlays)
        if clear_data:
            self.vm_mgr.load_all()
            for vm in self.vm_mgr.list_vms():
                if vm.vm_type != VM_TYPE_TEMPLATEVM and vm.id != "debian-template":
                    try:
                        SeamlessAppLauncher.terminate_apps(vm.id, force=True)
                        VMProcessManager.stop_vm(vm.id, force=True)
                    except Exception:
                        pass
                    self.vm_mgr.delete_vm(vm.id)

            if VMS_DIR.exists():
                for item in VMS_DIR.iterdir():
                    if item.is_dir() and item.name != "debian-template":
                        shutil.rmtree(item, ignore_errors=True)

            self.vm_mgr.load_all()
            done_items.append("data")

        # 4. Clear templates
        if clear_templates:
            self.vm_mgr.load_all()
            for vm in self.vm_mgr.list_vms():
                if vm.vm_type == VM_TYPE_TEMPLATEVM or vm.id == "debian-template":
                    try:
                        SeamlessAppLauncher.terminate_apps(vm.id, force=True)
                        VMProcessManager.stop_vm(vm.id, force=True)
                    except Exception:
                        pass
                    self.vm_mgr.delete_vm(vm.id)

            tpl_dir = VMS_DIR / "debian-template"
            if tpl_dir.exists():
                shutil.rmtree(tpl_dir, ignore_errors=True)

            self.vm_mgr.load_all()
            done_items.append("templates")

        # Refresh main window table if available
        if hasattr(self.parent_window, "_refresh_table"):
            self.parent_window._refresh_table()

        # Reset checkboxes
        self.chk_cache.set_active(False)
        self.chk_logs.set_active(False)
        self.chk_data.set_active(False)
        self.chk_templates.set_active(False)

        self.lbl_feedback.set_markup(
            f"<span foreground='#2ecc71'>Cleared {', '.join(done_items)}.</span>"
        )


# Compatibility aliases
SettingsDialog = AppSettingsDialog
