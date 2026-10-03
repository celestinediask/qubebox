"""VM Details Dialog showing full security and hardware specifications."""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from qubebox.core.process import VMProcessManager
from qubebox.core.vm import VMConfig


class VMDetailsDialog(Gtk.Dialog):
    def __init__(self, parent: Gtk.Window, vm: VMConfig):
        super().__init__(title=f"Qube Information - {vm.name}", transient_for=parent, flags=0)
        self.set_modal(True)
        self.set_default_size(480, 480)

        self.add_button("_Close", Gtk.ResponseType.CLOSE)

        box = self.get_content_area()
        box.set_spacing(14)
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_top(15)
        box.set_margin_bottom(15)

        # Header with color icon
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        color_area = Gtk.DrawingArea()
        color_area.set_size_request(24, 24)
        color_area.connect("draw", self._draw_color_pill, vm.get_color_hex())
        header_box.pack_start(color_area, False, False, 0)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lbl_title = Gtk.Label()
        lbl_title.set_markup(f"<b><big>{vm.name}</big></b>")
        lbl_title.set_xalign(0.0)
        title_box.pack_start(lbl_title, False, False, 0)

        status = VMProcessManager.get_status(vm.id)
        status_text = {
            "running": "<span foreground='#2ecc71'>● Running</span>",
            "stopped": "<span foreground='#7f8c8d'>○ Stopped</span>",
            "restarting": "<span foreground='#f1c40f'>◐ Restarting</span>",
            "error": "<span foreground='#e74c3c'>✕ Error</span>",
        }.get(status, "<span foreground='#7f8c8d'>○ Stopped</span>")

        lbl_status = Gtk.Label()
        lbl_status.set_markup(f"Status: {status_text} • Domain: {vm.color}")
        lbl_status.set_xalign(0.0)
        title_box.pack_start(lbl_status, False, False, 0)

        header_box.pack_start(title_box, True, True, 0)
        box.pack_start(header_box, False, False, 0)

        # Spec Card
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.get_style_context().add_class("card-box")

        grid = Gtk.Grid()
        grid.set_column_spacing(20)
        grid.set_row_spacing(8)

        def add_row(lbl, val, r):
            l = Gtk.Label(label=lbl)
            l.set_xalign(0.0)
            l.get_style_context().add_class("subtitle")
            v = Gtk.Label(label=str(val))
            v.set_xalign(0.0)
            grid.attach(l, 0, r, 1, 1)
            grid.attach(v, 1, r, 1, 1)

        add_row("Qube ID:", vm.id, 0)
        add_row("Virtualization Type:", vm.vm_type, 1)
        add_row("Security Label / Color:", vm.color, 2)
        add_row("Template Source:", vm.template or "Standalone (Direct)", 3)
        add_row("vCPUs:", f"{vm.cpus} Cores", 4)
        add_row("Memory:", f"{vm.memory_mb} MB", 5)
        add_row("User Private Storage:", f"{vm.storage_gb} GB", 6)
        add_row("Network Isolation:", vm.network.capitalize(), 7)
        add_row("Seamless Border:", "Enabled (4px)" if vm.seamless_mode else "Disabled", 8)
        if vm.iso_path:
            add_row("Boot/Install ISO:", vm.iso_path, 9)

        card.pack_start(grid, True, True, 0)
        box.pack_start(card, True, True, 0)

        self.show_all()

    def _draw_color_pill(self, widget, cr, color_hex):
        rgba = Gdk.RGBA()
        rgba.parse(color_hex)
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, 1.0)
        cr.arc(12, 12, 10, 0, 2 * 3.14159)
        cr.fill()
        return False
