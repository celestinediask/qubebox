"""Unified Qube Configuration Dialog for Creating and Editing Qubes."""

import os
import uuid
from typing import Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from qubebox.core.constants import (
    COLOR_MAP,
    NET_MODE_DEFAULT,
    NET_MODE_NONE,
    NET_MODE_RESTRICTED,
    QUBES_COLORS,
    VM_TYPE_APPVM,
    VM_TYPE_DISPVM,
    VM_TYPE_STANDALONEVM,
    VM_TYPE_TEMPLATEVM,
    VM_TYPES,
)
from qubebox.core.vm import VMConfig, VMManager


class QubeConfigDialog(Gtk.Dialog):
    """Single, unified, lightweight dialog for both creating and editing a Qube."""

    def __init__(
        self,
        parent: Gtk.Window,
        vm_mgr: VMManager,
        vm: Optional[VMConfig] = None,
        default_iso: str = "",
    ):
        self.is_edit_mode = vm is not None
        self.vm = vm
        self.vm_mgr = vm_mgr

        title = f"Qube Settings - {vm.name}" if self.is_edit_mode else "Create New Qube"
        super().__init__(title=title, transient_for=parent, flags=0)
        self.set_modal(True)
        self.set_default_size(420, -1)

        self.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        action_label = "_Save Settings" if self.is_edit_mode else "_Create Qube"
        self.action_btn = self.add_button(action_label, Gtk.ResponseType.OK)
        self.action_btn.get_style_context().add_class("suggested-action")

        box = self.get_content_area()
        box.set_spacing(8)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(12)
        box.set_margin_bottom(12)

        # Header title
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        if self.is_edit_mode:
            color_dot = Gtk.DrawingArea()
            color_dot.set_size_request(16, 16)
            color_dot.connect("draw", self._draw_color_pill, vm.get_color_hex())
            header_box.pack_start(color_dot, False, False, 0)

            title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            lbl_head = Gtk.Label()
            lbl_head.set_markup(f"<b><big>{vm.name}</big> Settings</b>")
            lbl_head.set_xalign(0.0)
            title_box.pack_start(lbl_head, False, False, 0)

            lbl_sub = Gtk.Label()
            lbl_sub.set_markup(f"<small>ID: {vm.id} • {vm.vm_type} • Domain: {vm.color}</small>")
            lbl_sub.set_xalign(0.0)
            title_box.pack_start(lbl_sub, False, False, 0)
            header_box.pack_start(title_box, True, True, 0)
        else:
            lbl_head = Gtk.Label()
            lbl_head.set_markup("<b><big>Create New Qube</big></b>")
            lbl_head.set_xalign(0.0)
            header_box.pack_start(lbl_head, True, True, 0)

        box.pack_start(header_box, False, False, 2)

        # Form grid
        grid = Gtk.Grid()
        grid.set_column_spacing(14)
        grid.set_row_spacing(8)
        box.pack_start(grid, True, True, 0)

        row = 0

        # 1. Qube Name
        lbl_name = Gtk.Label(label="Qube Name:")
        lbl_name.set_xalign(0.0)
        grid.attach(lbl_name, 0, row, 1, 1)

        self.entry_name = Gtk.Entry()
        self.entry_name.set_placeholder_text("e.g. untrusted, work, banking, debian-13")
        if self.is_edit_mode:
            self.entry_name.set_text(vm.name)
        self.entry_name.connect("changed", self._on_field_changed)
        grid.attach(self.entry_name, 1, row, 1, 1)
        row += 1

        # 2. Type (AppVM, TemplateVM, StandaloneVM, DispVM)
        lbl_type = Gtk.Label(label="Type:")
        lbl_type.set_xalign(0.0)
        grid.attach(lbl_type, 0, row, 1, 1)

        self.combo_type = Gtk.ComboBoxText()
        active_type_idx = 0
        for i, t in enumerate(VM_TYPES):
            self.combo_type.append_text(t)
            if self.is_edit_mode and t.lower() == vm.vm_type.lower():
                active_type_idx = i
        self.combo_type.set_active(active_type_idx)
        self.combo_type.connect("changed", self._on_type_changed)
        grid.attach(self.combo_type, 1, row, 1, 1)
        row += 1

        # 3. Label Color (Clean name only + info icon button with popover)
        lbl_color = Gtk.Label(label="Label Color:")
        lbl_color.set_xalign(0.0)
        grid.attach(lbl_color, 0, row, 1, 1)

        color_row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.combo_color = Gtk.ComboBoxText()
        active_color_idx = 0
        for i, c in enumerate(QUBES_COLORS):
            self.combo_color.append_text(c["name"])
            if self.is_edit_mode and c["name"].lower() == vm.color.lower():
                active_color_idx = i
        self.combo_color.set_active(active_color_idx)
        color_row_box.pack_start(self.combo_color, True, True, 0)

        # Info icon button with popover explaining color domains
        btn_color_info = Gtk.Button()
        img_info = Gtk.Image.new_from_icon_name("dialog-information-symbolic", Gtk.IconSize.MENU)
        btn_color_info.set_image(img_info)
        btn_color_info.set_tooltip_text("Security Domain Color Legend")
        btn_color_info.get_style_context().add_class("action-btn")

        popover_color = self._create_color_info_popover(btn_color_info)
        btn_color_info.connect("clicked", lambda b, p=popover_color: p.popup())
        color_row_box.pack_start(btn_color_info, False, False, 0)

        grid.attach(color_row_box, 1, row, 1, 1)
        row += 1

        # 4. Template (for AppVM / DispVM)
        self.lbl_template = Gtk.Label(label="Template:")
        self.lbl_template.set_xalign(0.0)
        grid.attach(self.lbl_template, 0, row, 1, 1)

        self.combo_template = Gtk.ComboBoxText()
        self._populate_templates()
        grid.attach(self.combo_template, 1, row, 1, 1)
        row += 1

        # 5. vCPUs
        lbl_cpu = Gtk.Label(label="vCPUs:")
        lbl_cpu.set_xalign(0.0)
        grid.attach(lbl_cpu, 0, row, 1, 1)

        self.spin_cpu = Gtk.SpinButton.new_with_range(1, 16, 1)
        self.spin_cpu.set_value(vm.cpus if self.is_edit_mode else 1)
        grid.attach(self.spin_cpu, 1, row, 1, 1)
        row += 1

        # 6. Memory (MB)
        lbl_mem = Gtk.Label(label="Memory (MB):")
        lbl_mem.set_xalign(0.0)
        grid.attach(lbl_mem, 0, row, 1, 1)

        self.spin_mem = Gtk.SpinButton.new_with_range(256, 32768, 256)
        self.spin_mem.set_value(vm.memory_mb if self.is_edit_mode else 512)
        grid.attach(self.spin_mem, 1, row, 1, 1)
        row += 1

        # 7. Private / Disk Storage (GB)
        self.lbl_storage = Gtk.Label(label="Private Storage (GB):")
        self.lbl_storage.set_xalign(0.0)
        grid.attach(self.lbl_storage, 0, row, 1, 1)

        self.spin_storage = Gtk.SpinButton.new_with_range(1, 500, 1)
        self.spin_storage.set_value(vm.storage_gb if self.is_edit_mode else 2)
        grid.attach(self.spin_storage, 1, row, 1, 1)
        row += 1

        # 8. Networking (sys-net (default), None)
        lbl_net = Gtk.Label(label="Networking:")
        lbl_net.set_xalign(0.0)
        grid.attach(lbl_net, 0, row, 1, 1)

        self.combo_net = Gtk.ComboBoxText()
        self.combo_net.append(NET_MODE_DEFAULT, "sys-net (default)")
        self.combo_net.append(NET_MODE_NONE, "None (air-gapped)")
        self.combo_net.append(NET_MODE_RESTRICTED, "Isolated (local only)")
        active_net = vm.network if self.is_edit_mode and vm.network else NET_MODE_DEFAULT
        self.combo_net.set_active_id(active_net)
        grid.attach(self.combo_net, 1, row, 1, 1)
        row += 1

        # 9. Installation ISO (Optional for Template/Standalone)
        self.lbl_iso = Gtk.Label(label="Installation ISO:")
        self.lbl_iso.set_xalign(0.0)
        grid.attach(self.lbl_iso, 0, row, 1, 1)

        self.iso_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.entry_iso = Gtk.Entry()
        self.entry_iso.set_hexpand(True)
        iso_init = vm.iso_path if (self.is_edit_mode and vm.iso_path) else default_iso
        if iso_init:
            self.entry_iso.set_text(iso_init)
        btn_browse_iso = Gtk.Button(label="Browse...")
        btn_browse_iso.connect("clicked", self._on_browse_iso)
        self.iso_box.pack_start(self.entry_iso, True, True, 0)
        self.iso_box.pack_start(btn_browse_iso, False, False, 0)
        grid.attach(self.iso_box, 1, row, 1, 1)
        row += 1

        self.show_all()
        self._on_type_changed(self.combo_type)
        self._on_field_changed(self.entry_name)

    def _draw_color_pill(self, widget, cr, color_hex):
        rgba = Gdk.RGBA()
        rgba.parse(color_hex)
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, 1.0)
        cr.arc(8, 8, 6.5, 0, 2 * 3.14159)
        cr.fill()
        return False

    def _create_color_info_popover(self, parent_btn: Gtk.Button) -> Gtk.Popover:
        popover = Gtk.Popover.new(parent_btn)
        popover.set_position(Gtk.PositionType.BOTTOM)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        vbox.set_margin_top(8)
        vbox.set_margin_bottom(8)

        lbl_head = Gtk.Label()
        lbl_head.set_markup("<b>Security Domain Colors</b>")
        lbl_head.set_xalign(0.0)
        vbox.pack_start(lbl_head, False, False, 2)

        for c in QUBES_COLORS:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            dot = Gtk.Label()
            dot.set_markup(f"<span foreground='{c['hex']}'>●</span> <b>{c['name']}:</b>")
            dot.set_xalign(0.0)
            lbl_desc = Gtk.Label(label=c["desc"])
            lbl_desc.set_xalign(0.0)
            row.pack_start(dot, False, False, 0)
            row.pack_start(lbl_desc, False, False, 0)
            vbox.pack_start(row, False, False, 0)

        popover.add(vbox)
        vbox.show_all()
        return popover

    def _populate_templates(self):
        self.combo_template.remove_all()
        templates = self.vm_mgr.get_templates()
        active_idx = 0
        for i, tpl in enumerate(templates):
            self.combo_template.append(tpl.id, f"{tpl.name} ({tpl.vm_type})")
            if self.is_edit_mode and (tpl.id == self.vm.template or tpl.name == self.vm.template):
                active_idx = i
        if templates:
            self.combo_template.set_active(active_idx)

    def _on_type_changed(self, combo):
        vtype = combo.get_active_text()
        if vtype in (VM_TYPE_APPVM, VM_TYPE_DISPVM):
            self.lbl_template.set_visible(True)
            self.combo_template.set_visible(True)
            self.lbl_storage.set_text("Private Storage (GB):")
            self.lbl_iso.set_visible(False)
            self.iso_box.set_visible(False)
        else:
            self.lbl_template.set_visible(False)
            self.combo_template.set_visible(False)
            self.lbl_storage.set_text("System Disk Size (GB):")
            self.lbl_iso.set_visible(True)
            self.iso_box.set_visible(True)

        if not self.is_edit_mode:
            # Color presets suggestion based on type
            if vtype == VM_TYPE_TEMPLATEVM:
                self.combo_color.set_active(6)  # Gray
            elif vtype == VM_TYPE_DISPVM:
                self.combo_color.set_active(1)  # Orange
            elif vtype == VM_TYPE_STANDALONEVM:
                self.combo_color.set_active(4)  # Blue

    def _on_field_changed(self, entry):
        name = entry.get_text().strip()
        self.action_btn.set_sensitive(len(name) > 0)

    def _on_browse_iso(self, btn):
        dialog = Gtk.FileChooserDialog(
            title="Select ISO Image",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        filter_iso = Gtk.FileFilter()
        filter_iso.set_name("Disk Images (*.iso, *.img, *.qcow2)")
        filter_iso.add_pattern("*.iso")
        filter_iso.add_pattern("*.img")
        filter_iso.add_pattern("*.qcow2")
        dialog.add_filter(filter_iso)

        if dialog.run() == Gtk.ResponseType.OK:
            self.entry_iso.set_text(dialog.get_filename())
        dialog.destroy()

    def get_vm_config(self) -> VMConfig:
        """Returns new VMConfig (for creation mode) or updated VMConfig (for edit mode)."""
        name = self.entry_name.get_text().strip()
        vm_type = self.combo_type.get_active_text()
        color_idx = max(0, self.combo_color.get_active())
        color_name = QUBES_COLORS[color_idx]["name"]
        template_id = self.combo_template.get_active_id() or ""
        iso_val = self.entry_iso.get_text().strip() if vm_type not in (VM_TYPE_APPVM, VM_TYPE_DISPVM) else ""

        if self.is_edit_mode:
            self.vm.name = name
            self.vm.vm_type = vm_type
            self.vm.color = color_name
            if vm_type in (VM_TYPE_APPVM, VM_TYPE_DISPVM):
                self.vm.template = template_id
            self.vm.cpus = int(self.spin_cpu.get_value())
            self.vm.memory_mb = int(self.spin_mem.get_value())
            self.vm.storage_gb = int(self.spin_storage.get_value())
            self.vm.network = self.combo_net.get_active_id() or NET_MODE_DEFAULT
            if vm_type not in (VM_TYPE_APPVM, VM_TYPE_DISPVM):
                self.vm.iso_path = iso_val
            return self.vm

        return VMConfig(
            id=str(uuid.uuid4())[:8],
            name=name,
            vm_type=vm_type,
            color=color_name,
            template=template_id,
            cpus=int(self.spin_cpu.get_value()),
            memory_mb=int(self.spin_mem.get_value()),
            storage_gb=int(self.spin_storage.get_value()),
            network=self.combo_net.get_active_id() or NET_MODE_DEFAULT,
            iso_path=iso_val,
            seamless_mode=True,
            border_width=4,
        )

    def save_changes(self) -> VMConfig:
        """Convenience method for edit mode saving."""
        vm = self.get_vm_config()
        self.vm_mgr.save_vm(vm)
        return vm


# Aliases for backward compatibility
CreateVMDialog = QubeConfigDialog
VMSettingsDialog = QubeConfigDialog
