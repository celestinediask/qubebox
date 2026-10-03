"""QubeBox application entry point."""

import os
import sys
from pathlib import Path

# Setup paths
SRC_DIR = Path(__file__).resolve().parent.parent
APP_ROOT = SRC_DIR.parent

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Ensure runtime paths for rootless QEMU execution
runtime_dir = APP_ROOT / "runtime"
if runtime_dir.exists():
    bin_dir = runtime_dir / "bin"
    lib_dir = runtime_dir / "lib"
    os.environ["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"
    os.environ["LD_LIBRARY_PATH"] = f"{lib_dir}:{os.environ.get('LD_LIBRARY_PATH', '')}"
    if (lib_dir / "qemu").exists():
        os.environ["QEMU_MODULE_DIR"] = str(lib_dir / "qemu")

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from qubebox.ui.css import DARK_THEME_CSS
from qubebox.ui.main_window import MainWindow


class QubeBoxApplication(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="org.qubebox.manager",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self._apply_dark_theme()

    def do_activate(self):
        win = MainWindow(self)
        win.show_all()

    def _apply_dark_theme(self):
        settings = Gtk.Settings.get_default()
        if settings:
            settings.set_property("gtk-application-prefer-dark-theme", True)
            settings.set_property("gtk-theme-name", "Adwaita-dark")

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(DARK_THEME_CSS.encode("utf-8"))
        screen = Gdk.Screen.get_default()
        if screen:
            Gtk.StyleContext.add_provider_for_screen(
                screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )


def main():
    app = QubeBoxApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
