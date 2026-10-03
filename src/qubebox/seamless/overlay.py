"""Cairo-drawn Border Overlay Window with input transparency and shape clipping."""

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk


class BorderOverlayWindow(Gtk.Window):
    """
    A top-level border overlay window that frames a target VM window
    with QubesOS-level color identification, while passing mouse clicks
    through the center directly into the VM window and clipping occluded edges.
    """

    def __init__(self, color_hex: str = "#e74c3c", border_width: int = 4, title_label: str = ""):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_keep_above(False)
        self.set_accept_focus(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)

        self.color_hex = color_hex
        self.border_width = border_width
        self.title_label = title_label

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)

        self.connect("draw", self.on_draw)

    def on_draw(self, widget, cr):
        # Clear background completely
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        # Fill the visible unoccluded border area defined by shape_combine_region
        rgba = Gdk.RGBA()
        rgba.parse(self.color_hex)
        cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, 0.95)
        cr.paint()

        return False

    def update_geometry(
        self,
        fx: int,
        fy: int,
        fw: int,
        fh: int,
        occluding_rects=None
    ):
        bw = self.border_width
        ox = fx - bw
        oy = fy - bw
        ow = fw + 2 * bw
        oh = fh + 2 * bw

        # Build border frame region (outer minus hollow inner)
        outer_rect = cairo.RectangleInt(0, 0, ow, oh)
        border_region = cairo.Region(outer_rect)
        inner_rect = cairo.RectangleInt(bw, bw, fw, fh)
        border_region.subtract(inner_rect)

        # Subtract any windows stacked above this window to prevent overlapping borders
        if occluding_rects:
            for cx, cy, cw, ch in occluding_rects:
                if cx < ox + ow and cx + cw > ox and cy < oy + oh and cy + ch > oy:
                    clip_rect = cairo.RectangleInt(cx - ox, cy - oy, cw, ch)
                    border_region.subtract(clip_rect)

        if border_region.is_empty():
            self.hide()
            return

        self.show()
        gdk_win = self.get_window()
        if gdk_win:
            gdk_win.move_resize(ox, oy, ow, oh)
            gdk_win.shape_combine_region(border_region, 0, 0)
            gdk_win.input_shape_combine_region(cairo.Region(), 0, 0)

        self.queue_draw()
