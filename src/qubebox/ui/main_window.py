"""Main Application Window for QubeBox with Table View, App Launcher Menu, and Icon Actions."""

import os
from pathlib import Path
from typing import Dict, List, Optional

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from qubebox.core.constants import (
    COLOR_MAP,
    VM_TYPE_APPVM,
    VM_TYPE_DISPVM,
    VM_TYPE_STANDALONEVM,
    VM_TYPE_TEMPLATEVM,
)
from qubebox.core.detector import SystemDetector
from qubebox.core.process import VMProcessManager
from qubebox.core.seamless_launcher import SeamlessAppLauncher
from qubebox.core.vm import VMConfig, VMManager
from qubebox.seamless.tracker import SeamlessTracker
from qubebox.ui.create_dialog import QubeConfigDialog
from qubebox.ui.details_dialog import VMDetailsDialog
from qubebox.ui.settings_dialog import AppSettingsDialog


class MainWindow(Gtk.ApplicationWindow):
    # Column width specifications for strict header-to-item vertical alignment
    COL_STATUS = 48
    COL_NAME = 120
    COL_ACTIONS = 260
    COL_TYPE = 95
    COL_TEMPLATE = 105
    COL_CPU = 50
    COL_MEMORY = 75
    COL_STORAGE = 75

    def __init__(self, app: Gtk.Application):
        super().__init__(title="QubeBox - QubesOS VM Manager", application=app)
        self.set_default_size(505, 540)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Register custom symbolic icon assets
        assets_dir = Path(__file__).parent.parent / "assets"
        if assets_dir.exists():
            Gtk.IconTheme.get_default().append_search_path(str(assets_dir))

        self.vm_mgr = VMManager()
        self.tracker = SeamlessTracker()
        self.tracker.start()
        self.action_widgets: Dict[str, Dict[str, Gtk.Widget]] = {}

        self._build_table_ui()
        self._refresh_table()

        # Regular poll to refresh status dots and button sensitivities
        GLib.timeout_add(1000, self._on_status_poll)

    def _build_table_ui(self):
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root_box)

        # Lightweight Classic Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.get_style_context().add_class("classic-toolbar")
        toolbar.set_margin_start(16)
        toolbar.set_margin_end(16)
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(6)

        lbl_app_title = Gtk.Label()
        lbl_app_title.set_markup("<b>Qubes</b>")
        lbl_app_title.set_xalign(0.0)
        toolbar.pack_start(lbl_app_title, False, False, 0)

        # Expanding spacer to move buttons to right side
        spacer = Gtk.Box()
        toolbar.pack_start(spacer, True, True, 0)

        # Refresh Button (icon only)
        btn_refresh = Gtk.Button()
        icon_ref = Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.MENU)
        btn_refresh.set_image(icon_ref)
        btn_refresh.get_style_context().add_class("toolbar-icon-btn")
        btn_refresh.set_tooltip_text("Refresh Virtual Machines and Statuses")
        btn_refresh.connect("clicked", lambda b: self._refresh_table())
        toolbar.pack_start(btn_refresh, False, False, 0)

        # Create Qube Button (icon only)
        btn_new = Gtk.Button()
        icon_add = Gtk.Image.new_from_icon_name("list-add-symbolic", Gtk.IconSize.MENU)
        btn_new.set_image(icon_add)
        btn_new.get_style_context().add_class("toolbar-icon-btn")
        btn_new.set_tooltip_text("Create New Virtual Machine (Qube)")
        btn_new.connect("clicked", self._on_new_vm_clicked)
        toolbar.pack_start(btn_new, False, False, 0)

        # Settings Button (icon only)
        btn_settings = Gtk.Button()
        icon_settings = Gtk.Image.new_from_icon_name("settings-simple-symbolic", Gtk.IconSize.MENU)
        btn_settings.set_image(icon_settings)
        btn_settings.get_style_context().add_class("toolbar-icon-btn")
        btn_settings.set_tooltip_text("Settings & Clean Slate Maintenance")
        btn_settings.connect("clicked", self._on_app_settings_clicked)
        toolbar.pack_start(btn_settings, False, False, 0)

        root_box.pack_start(toolbar, False, False, 0)
        sep_top = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        root_box.pack_start(sep_top, False, False, 0)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_kinetic_scrolling(True)
        self.scroll.set_overlay_scrolling(True)
        self.scroll.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.scroll.connect("scroll-event", self._on_scroll_event)
        root_box.pack_start(self.scroll, True, True, 0)

        # Main Table Container
        self.table_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.table_box.get_style_context().add_class("table-container")
        self.scroll.add(self.table_box)

        # Status Bar at bottom
        self.statusbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self.statusbar.set_margin_start(16)
        self.statusbar.set_margin_end(16)
        self.statusbar.set_margin_top(8)
        self.statusbar.set_margin_bottom(8)
        self.lbl_status_summary = Gtk.Label()
        self.lbl_status_summary.set_xalign(0.0)
        self.statusbar.pack_start(self.lbl_status_summary, True, True, 0)
        root_box.pack_end(self.statusbar, False, False, 0)

    def _on_scroll_event(self, widget, event):
        hadj = widget.get_hadjustment()
        if not hadj:
            return False
        if event.direction == Gdk.ScrollDirection.SMOOTH:
            has_dx, dx, dy = event.get_scroll_deltas()
            if has_dx and abs(dx) > 0.001:
                step = hadj.get_step_increment() or 25.0
                new_val = hadj.get_value() + dx * step
                hadj.set_value(max(hadj.get_lower(), min(new_val, hadj.get_upper() - hadj.get_page_size())))
                return True
        elif event.direction == Gdk.ScrollDirection.LEFT:
            step = hadj.get_step_increment() or 30.0
            hadj.set_value(max(hadj.get_lower(), hadj.get_value() - step))
            return True
        elif event.direction == Gdk.ScrollDirection.RIGHT:
            step = hadj.get_step_increment() or 30.0
            hadj.set_value(min(hadj.get_upper() - hadj.get_page_size(), hadj.get_value() + step))
            return True
        return False

    def _create_header_row(self) -> Gtk.Widget:
        header_grid = Gtk.Grid()
        header_grid.set_column_spacing(10)
        header_grid.set_margin_start(16)
        header_grid.set_margin_end(16)
        header_grid.set_margin_top(10)
        header_grid.set_margin_bottom(8)

        def make_th(text, width, xalign=0.0):
            lbl = Gtk.Label()
            lbl.set_markup(f"<b>{text.upper()}</b>")
            lbl.set_xalign(xalign)
            lbl.set_size_request(width, -1)
            lbl.get_style_context().add_class("th-label")
            return lbl

        header_grid.attach(make_th("Status", self.COL_STATUS, xalign=0.5), 0, 0, 1, 1)
        header_grid.attach(make_th("Qube Name", self.COL_NAME), 1, 0, 1, 1)
        header_grid.attach(make_th("Actions", self.COL_ACTIONS), 2, 0, 1, 1)
        header_grid.attach(make_th("Type", self.COL_TYPE), 3, 0, 1, 1)
        header_grid.attach(make_th("Template", self.COL_TEMPLATE), 4, 0, 1, 1)
        header_grid.attach(make_th("CPU", self.COL_CPU), 5, 0, 1, 1)
        header_grid.attach(make_th("Memory", self.COL_MEMORY), 6, 0, 1, 1)
        header_grid.attach(make_th("Storage", self.COL_STORAGE), 7, 0, 1, 1)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        container.pack_start(header_grid, False, False, 0)
        container.pack_start(sep, False, False, 0)
        return container

    def _draw_status_dot(self, widget, cr, status: str):
        # Colors: Grey for off, green for running, yellow for restarting/paused, red for error
        color_map = {
            "running": (46 / 255.0, 204 / 255.0, 113 / 255.0),    # #2ecc71 Green
            "stopped": (127 / 255.0, 140 / 255.0, 141 / 255.0),  # #7f8c8d Grey
            "restarting": (241 / 255.0, 196 / 255.0, 15 / 255.0), # #f1c40f Yellow
            "paused": (52 / 255.0, 152 / 255.0, 219 / 255.0),    # #3498db Blue
            "error": (231 / 255.0, 76 / 255.0, 60 / 255.0),       # #e74c3c Red
        }
        r, g, b = color_map.get(status, (127 / 255.0, 140 / 255.0, 141 / 255.0))

        alloc = widget.get_allocation()
        cx = alloc.width / 2.0
        cy = alloc.height / 2.0

        cr.set_source_rgb(r, g, b)
        cr.arc(cx, cy, 5.0, 0, 2 * 3.14159)
        cr.fill()
        return False

    def _create_action_icon_btn(self, icon_name: str, tooltip: str, css_class: str, on_click=None) -> Gtk.Button:
        btn = Gtk.Button()
        img = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        btn.set_image(img)
        btn.set_tooltip_text(tooltip)
        btn.get_style_context().add_class("action-btn")
        if css_class:
            btn.get_style_context().add_class(css_class)
        if on_click:
            btn.connect("clicked", on_click)
        return btn

    def _create_app_popover(self, parent_btn: Gtk.Button, vm: VMConfig) -> Gtk.Popover:
        popover = Gtk.Popover.new(parent_btn)
        popover.set_position(Gtk.PositionType.BOTTOM)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox.set_margin_start(8)
        vbox.set_margin_end(8)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)

        # Header title
        lbl_head = Gtk.Label()
        lbl_head.set_markup(f"<small><b>Run App in <span foreground='{vm.get_color_hex()}'>{vm.name}</span></b></small>")
        lbl_head.set_xalign(0.0)
        vbox.pack_start(lbl_head, False, False, 4)

        apps = [
            ("utilities-terminal-symbolic", "Terminal", "xfce4-terminal"),
            ("system-file-manager-symbolic", "File Manager", "thunar"),
            ("web-browser-symbolic", "Firefox Browser", "firefox-esr"),
            ("preferences-system-symbolic", "XFCE4 Settings", "xfce4-settings-manager"),
        ]

        for icon_name, app_label, cmd in apps:
            item_btn = Gtk.Button()
            item_btn.get_style_context().add_class("app-menu-item")
            
            box_item = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            img = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
            lbl = Gtk.Label(label=app_label)
            lbl.set_xalign(0.0)

            box_item.pack_start(img, False, False, 0)
            box_item.pack_start(lbl, True, True, 0)
            item_btn.add(box_item)

            item_btn.connect("clicked", lambda b, v=vm, c=cmd, p=popover: self._on_launch_app(v, c, p))
            vbox.pack_start(item_btn, False, False, 0)

        popover.add(vbox)
        vbox.show_all()
        return popover

    def _on_launch_app(self, vm: VMConfig, command: str, popover: Gtk.Popover):
        popover.popdown()
        try:
            SeamlessAppLauncher.launch(vm, self.vm_mgr, command)
            self.tracker.register_vm(vm)
            self._update_vm_row_state(vm.id)
            print(f"Launched '{command}' in Qube '{vm.name}'")
        except Exception as e:
            dlg = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=f"Failed to launch app in Qube '{vm.name}'",
            )
            dlg.format_secondary_text(str(e))
            dlg.run()
            dlg.destroy()

    def _refresh_table(self):
        for child in self.table_box.get_children():
            self.table_box.remove(child)

        self.action_widgets.clear()
        self.table_box.pack_start(self._create_header_row(), False, False, 0)

        vms = self.vm_mgr.list_vms()
        running_count = 0

        if not vms:
            empty_lbl = Gtk.Label()
            empty_lbl.set_markup("\n<big><b>No Qubes Found</b></big>\n<small>Click '+' to create a new Qube</small>\n")
            self.table_box.pack_start(empty_lbl, True, True, 20)
            self.table_box.show_all()
            self.lbl_status_summary.set_text("Total Qubes: 0")
            return

        for vm in vms:
            self.tracker.register_vm(vm)
            status = VMProcessManager.get_status(vm.id)
            if status in ("running", "paused"):
                running_count += 1

            row_grid = Gtk.Grid()
            row_grid.set_column_spacing(10)
            row_grid.set_margin_start(16)
            row_grid.set_margin_end(16)
            row_grid.set_margin_top(7)
            row_grid.set_margin_bottom(7)

            # 1. Running Status Dot
            status_dot = Gtk.DrawingArea()
            status_dot.set_size_request(self.COL_STATUS, 24)
            status_dot.set_tooltip_text(f"Status: {status.capitalize()}")
            status_dot.connect("draw", self._draw_status_dot, status)
            row_grid.attach(status_dot, 0, 0, 1, 1)

            # 2. Qube Name with Security Color (Left aligned, strict matching width)
            lbl_name = Gtk.Label()
            lbl_name.set_markup(f"<span foreground='{vm.get_color_hex()}'><b>{vm.name}</b></span>")
            lbl_name.set_size_request(self.COL_NAME, -1)
            lbl_name.set_xalign(0.0)
            lbl_name.set_tooltip_text(f"Security Domain: {vm.color}")
            row_grid.attach(lbl_name, 1, 0, 1, 1)

            # 3. Action Icons: Play/Pause, Stop, Restart, Kill, Run App, Settings, Delete, Info
            actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
            actions_box.set_size_request(self.COL_ACTIONS, -1)

            if status == "running":
                play_icon = "media-playback-pause-symbolic"
                play_tooltip = "Pause Execution"
            elif status == "paused":
                play_icon = "media-playback-start-symbolic"
                play_tooltip = "Resume Execution"
            else:
                play_icon = "media-playback-start-symbolic"
                play_tooltip = "Start Qube"

            btn_play_pause = self._create_action_icon_btn(
                play_icon, play_tooltip, "action-btn-green",
                lambda b, v=vm: self._on_play_pause_vm(v)
            )
            btn_stop = self._create_action_icon_btn(
                "media-playback-stop-symbolic", "Graceful Shutdown (ACPI)", "action-btn-yellow",
                lambda b, v=vm: self._on_stop_vm(v, force=False)
            )
            btn_restart = self._create_action_icon_btn(
                "system-reboot-symbolic", "Restart Qube", "action-btn-blue",
                lambda b, v=vm: self._on_restart_vm(v)
            )
            btn_kill = self._create_action_icon_btn(
                "process-stop-symbolic", "Force Kill", "action-btn-red",
                lambda b, v=vm: self._on_stop_vm(v, force=True)
            )

            # Run App Icon & Popover Menu (simple app-grid icon)
            btn_run_app = self._create_action_icon_btn(
                "view-grid-symbolic", "Run Application in Qube...", "action-btn-blue",
                None
            )
            popover_apps = self._create_app_popover(btn_run_app, vm)
            btn_run_app.connect("clicked", lambda b, p=popover_apps: p.popup())

            # Settings Icon & Dialog (clean simple gear icon)
            btn_settings = self._create_action_icon_btn(
                "settings-simple-symbolic", "Edit Qube Settings & Configuration...", "action-btn-blue",
                lambda b, v=vm: self._on_edit_settings(v)
            )

            btn_del = self._create_action_icon_btn(
                "user-trash-symbolic", "Delete Qube", "action-btn-red",
                lambda b, v=vm: self._on_delete_vm(v)
            )

            # Info Icon (View Specs) placed directly after Delete icon
            btn_info = self._create_action_icon_btn(
                "dialog-information-symbolic", "View Qube Details & Specs", "action-btn-blue",
                lambda b, v=vm: self._on_view_details(v)
            )

            # Configure initial sensitivity based on status
            is_active = (status in ("running", "paused", "restarting"))
            btn_stop.set_sensitive(is_active)
            btn_restart.set_sensitive(is_active)
            btn_kill.set_sensitive(is_active)
            btn_del.set_sensitive(not is_active)

            actions_box.pack_start(btn_play_pause, False, False, 0)
            actions_box.pack_start(btn_stop, False, False, 0)
            actions_box.pack_start(btn_restart, False, False, 0)
            actions_box.pack_start(btn_kill, False, False, 0)
            actions_box.pack_start(btn_run_app, False, False, 0)
            actions_box.pack_start(btn_settings, False, False, 0)
            actions_box.pack_start(btn_del, False, False, 0)
            actions_box.pack_start(btn_info, False, False, 0)
            row_grid.attach(actions_box, 2, 0, 1, 1)

            # 4. Type (Left aligned, matching width)
            lbl_type = Gtk.Label(label=vm.vm_type)
            lbl_type.set_size_request(self.COL_TYPE, -1)
            lbl_type.set_xalign(0.0)
            lbl_type.get_style_context().add_class("type-label")
            row_grid.attach(lbl_type, 3, 0, 1, 1)

            # 5. Template (Left aligned, matching width)
            lbl_tpl = Gtk.Label(label=vm.template if vm.template else "—")
            lbl_tpl.set_size_request(self.COL_TEMPLATE, -1)
            lbl_tpl.set_xalign(0.0)
            row_grid.attach(lbl_tpl, 4, 0, 1, 1)

            # 6. CPU (Left aligned, matching width)
            lbl_cpu = Gtk.Label(label=str(vm.cpus))
            lbl_cpu.set_size_request(self.COL_CPU, -1)
            lbl_cpu.set_xalign(0.0)
            row_grid.attach(lbl_cpu, 5, 0, 1, 1)

            # 7. Memory (Left aligned, matching width)
            lbl_mem = Gtk.Label(label=f"{vm.memory_mb} MB")
            lbl_mem.set_size_request(self.COL_MEMORY, -1)
            lbl_mem.set_xalign(0.0)
            row_grid.attach(lbl_mem, 6, 0, 1, 1)

            # 8. Storage (Left aligned, matching width)
            lbl_storage = Gtk.Label(label=f"{vm.storage_gb} GB")
            lbl_storage.set_size_request(self.COL_STORAGE, -1)
            lbl_storage.set_xalign(0.0)
            row_grid.attach(lbl_storage, 7, 0, 1, 1)

            # Store references to dynamically update sensitivities & status dot
            self.action_widgets[vm.id] = {
                "status_dot": status_dot,
                "btn_play_pause": btn_play_pause,
                "btn_stop": btn_stop,
                "btn_restart": btn_restart,
                "btn_kill": btn_kill,
                "btn_run_app": btn_run_app,
                "btn_settings": btn_settings,
                "btn_del": btn_del,
                "btn_info": btn_info,
                "current_status": status,
            }

            row_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            row_container.pack_start(row_grid, False, False, 0)
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            row_container.pack_start(sep, False, False, 0)
            self.table_box.pack_start(row_container, False, False, 0)

        self.table_box.show_all()
        self.lbl_status_summary.set_markup(
            f"<b>Total Qubes:</b> {len(vms)}   |   <span foreground='#2ecc71'>● <b>Running:</b> {running_count}</span>   |   <span foreground='#7f8c8d'>○ <b>Stopped:</b> {len(vms) - running_count}</span>"
        )

    def _on_play_pause_vm(self, vm: VMConfig):
        status = VMProcessManager.get_status(vm.id)
        if status == "running":
            self._on_toggle_pause_vm(vm)
        elif status == "paused":
            self._on_toggle_pause_vm(vm)
        else:
            self._on_start_vm(vm)

    def _on_start_vm(self, vm: VMConfig):
        try:
            headless = not bool(vm.iso_path and Path(vm.iso_path).exists())
            VMProcessManager.start_vm(vm, self.vm_mgr, headless=headless)
            self.tracker.register_vm(vm)
            self._update_vm_row_state(vm.id)
        except Exception as e:
            dlg = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=f"Failed to start Qube '{vm.name}'",
            )
            dlg.format_secondary_text(str(e))
            dlg.run()
            dlg.destroy()

    def _on_toggle_pause_vm(self, vm: VMConfig):
        VMProcessManager.toggle_pause_vm(vm.id, self.vm_mgr)
        self._update_vm_row_state(vm.id)

    def _on_stop_vm(self, vm: VMConfig, force: bool = False):
        SeamlessAppLauncher.terminate_apps(vm.id, force=force)
        VMProcessManager.stop_vm(vm.id, force=force, vm_mgr=self.vm_mgr)
        self.tracker.unregister_vm(vm.id)
        if vm.vm_type == VM_TYPE_DISPVM or vm.is_disposable_instance:
            self._refresh_table()
        else:
            self._update_vm_row_state(vm.id)

    def _on_restart_vm(self, vm: VMConfig):
        try:
            # Set state to restarting immediately to show yellow dot
            widgets = self.action_widgets.get(vm.id)
            if widgets:
                widgets["current_status"] = "restarting"
                widgets["status_dot"].queue_draw()
            
            GLib.idle_add(lambda: self._do_restart(vm))
        except Exception as e:
            print(f"Error initiating restart: {e}")

    def _do_restart(self, vm: VMConfig):
        try:
            headless = not bool(vm.iso_path and Path(vm.iso_path).exists())
            VMProcessManager.restart_vm(vm, self.vm_mgr, headless=headless)
            self.tracker.register_vm(vm)
        except Exception as e:
            dlg = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text=f"Failed to restart Qube '{vm.name}'",
            )
            dlg.format_secondary_text(str(e))
            dlg.run()
            dlg.destroy()
        finally:
            self._update_vm_row_state(vm.id)

    def _on_delete_vm(self, vm: VMConfig):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Delete Qube '{vm.name}'?",
        )
        dlg.format_secondary_text("This will permanently remove the virtual machine configuration and private disk storage.")
        resp = dlg.run()
        dlg.destroy()
        if resp == Gtk.ResponseType.YES:
            self.vm_mgr.delete_vm(vm.id)
            self._refresh_table()

    def _on_view_details(self, vm: VMConfig):
        dlg = VMDetailsDialog(self, vm)
        dlg.run()
        dlg.destroy()

    def _on_edit_settings(self, vm: VMConfig):
        dlg = QubeConfigDialog(self, self.vm_mgr, vm=vm)
        if dlg.run() == Gtk.ResponseType.OK:
            dlg.save_changes()
            self.tracker.register_vm(vm)
            self._refresh_table()
        dlg.destroy()

    def _on_new_vm_clicked(self, btn):
        dlg = QubeConfigDialog(self, self.vm_mgr, default_iso="")
        if dlg.run() == Gtk.ResponseType.OK:
            new_vm = dlg.get_vm_config()
            self.vm_mgr.save_vm(new_vm)
            self._refresh_table()
        dlg.destroy()

    def _on_app_settings_clicked(self, btn):
        dlg = AppSettingsDialog(self, self.vm_mgr)
        dlg.run()
        dlg.destroy()
        self._refresh_table()

    def _update_vm_row_state(self, vm_id: str):
        widgets = self.action_widgets.get(vm_id)
        if not widgets:
            return
        status = VMProcessManager.get_status(vm_id)
        widgets["current_status"] = status
        
        # Redraw status dot
        status_dot = widgets["status_dot"]
        status_dot.set_tooltip_text(f"Status: {status.capitalize()}")
        status_dot.disconnect_by_func(self._draw_status_dot)
        status_dot.connect("draw", self._draw_status_dot, status)
        status_dot.queue_draw()

        is_active = (status in ("running", "paused", "restarting"))
        widgets["btn_stop"].set_sensitive(is_active)
        widgets["btn_restart"].set_sensitive(is_active)
        widgets["btn_kill"].set_sensitive(is_active)
        widgets["btn_del"].set_sensitive(not is_active)

        # Update play/pause button icon and tooltip
        btn_play_pause = widgets["btn_play_pause"]
        if status == "running":
            play_icon = "media-playback-pause-symbolic"
            play_tooltip = "Pause Execution"
            btn_play_pause.set_sensitive(True)
        elif status == "paused":
            play_icon = "media-playback-start-symbolic"
            play_tooltip = "Resume Execution"
            btn_play_pause.set_sensitive(True)
        elif status == "restarting":
            play_icon = "media-playback-start-symbolic"
            play_tooltip = "Restarting..."
            btn_play_pause.set_sensitive(False)
        else:
            play_icon = "media-playback-start-symbolic"
            play_tooltip = "Start Qube"
            btn_play_pause.set_sensitive(True)

        btn_play_pause.set_tooltip_text(play_tooltip)
        btn_play_pause.set_image(Gtk.Image.new_from_icon_name(play_icon, Gtk.IconSize.MENU))

    def _on_status_poll(self) -> bool:
        vms = self.vm_mgr.list_vms()
        running_count = 0
        for vm in vms:
            status = VMProcessManager.get_status(vm.id)
            if status in ("running", "paused"):
                running_count += 1
            widgets = self.action_widgets.get(vm.id)
            if widgets and widgets.get("current_status") != status:
                self._update_vm_row_state(vm.id)

        self.lbl_status_summary.set_markup(
            f"<b>Total Qubes:</b> {len(vms)}   |   <span foreground='#2ecc71'>● <b>Running:</b> {running_count}</span>   |   <span foreground='#7f8c8d'>○ <b>Stopped:</b> {len(vms) - running_count}</span>"
        )
        return True
