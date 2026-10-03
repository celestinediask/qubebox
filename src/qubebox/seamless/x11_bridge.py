"""Low-level X11 Window Manager bridge using ctypes."""

import ctypes
from ctypes import (
    POINTER,
    Structure,
    byref,
    c_char_p,
    c_int,
    c_long,
    c_uint,
    c_ulong,
    c_void_p,
)
from typing import Dict, List, Optional, Tuple


class X11WindowInfo:
    def __init__(self, xid: int, title: str, x: int, y: int, width: int, height: int, pid: int = 0):
        self.xid = xid
        self.title = title
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.pid = pid


class XWindowChanges(Structure):
    _fields_ = [
        ("x", c_int),
        ("y", c_int),
        ("width", c_int),
        ("height", c_int),
        ("border_width", c_int),
        ("sibling", c_ulong),
        ("stack_mode", c_int),
    ]


class X11Bridge:
    """Provides pure-python X11 queries without external dependencies."""

    def __init__(self):
        try:
            self.x11 = ctypes.cdll.LoadLibrary("libX11.so.6")
            self._setup_prototypes()
            self._display = self.x11.XOpenDisplay(None)
        except Exception as e:
            print(f"X11Bridge initialization warning: {e}")
            self.x11 = None
            self._display = None

    def _setup_prototypes(self):
        self.x11.XOpenDisplay.restype = c_void_p
        self.x11.XCloseDisplay.argtypes = [c_void_p]
        self.x11.XDefaultRootWindow.argtypes = [c_void_p]
        self.x11.XDefaultRootWindow.restype = c_ulong
        self.x11.XQueryTree.argtypes = [
            c_void_p, c_ulong,
            POINTER(c_ulong), POINTER(c_ulong),
            POINTER(POINTER(c_ulong)), POINTER(c_uint)
        ]
        self.x11.XQueryTree.restype = c_int
        self.x11.XFree.argtypes = [c_void_p]
        self.x11.XFetchName.argtypes = [c_void_p, c_ulong, POINTER(c_char_p)]
        self.x11.XFetchName.restype = c_int

        self.x11.XGetGeometry.argtypes = [
            c_void_p, c_ulong,
            POINTER(c_ulong), POINTER(c_int), POINTER(c_int),
            POINTER(c_uint), POINTER(c_uint),
            POINTER(c_uint), POINTER(c_uint)
        ]
        self.x11.XGetGeometry.restype = c_int

        self.x11.XTranslateCoordinates.argtypes = [
            c_void_p, c_ulong, c_ulong,
            c_int, c_int,
            POINTER(c_int), POINTER(c_int),
            POINTER(c_ulong)
        ]
        self.x11.XTranslateCoordinates.restype = c_int

        self.x11.XInternAtom.argtypes = [c_void_p, c_char_p, c_int]
        self.x11.XInternAtom.restype = c_ulong

        self.x11.XGetWindowProperty.argtypes = [
            c_void_p, c_ulong, c_ulong,
            c_long, c_long, c_int, c_ulong,
            POINTER(c_ulong), POINTER(c_int),
            POINTER(c_ulong), POINTER(c_ulong),
            c_void_p
        ]
        self.x11.XGetWindowProperty.restype = c_int

        self.x11.XSetTransientForHint.argtypes = [c_void_p, c_ulong, c_ulong]
        self.x11.XSetTransientForHint.restype = c_int

        self.x11.XConfigureWindow.argtypes = [c_void_p, c_ulong, c_uint, POINTER(XWindowChanges)]
        self.x11.XConfigureWindow.restype = c_int

        self.x11.XRaiseWindow.argtypes = [c_void_p, c_ulong]
        self.x11.XRaiseWindow.restype = c_int

    def is_available(self) -> bool:
        return self._display is not None

    def raise_window(self, xid: int):
        if self._display and xid:
            self.x11.XRaiseWindow(self._display, c_ulong(xid))
            self.x11.XFlush(self._display)

    def get_active_window(self) -> int:
        if not self._display:
            return 0
        atom_active = self.x11.XInternAtom(self._display, b"_NET_ACTIVE_WINDOW", 0)
        atom_window = self.x11.XInternAtom(self._display, b"WINDOW", 0)
        actual_type, actual_format, nitems, bytes_after = c_ulong(), c_int(), c_ulong(), c_ulong()
        prop = c_void_p()
        root = self.x11.XDefaultRootWindow(self._display)
        res = self.x11.XGetWindowProperty(
            self._display, root, atom_active,
            0, 1, 0, atom_window,
            byref(actual_type), byref(actual_format),
            byref(nitems), byref(bytes_after), byref(prop)
        )
        active_xid = 0
        if res == 0 and prop.value:
            active_xid = ctypes.cast(prop.value, POINTER(c_ulong))[0]
            self.x11.XFree(prop.value)
        return active_xid

    def restack_above(self, window_xid: int, target_xid: int):
        """Restacks window_xid directly above target_xid in window hierarchy."""
        if not self._display or not window_xid or not target_xid:
            return
        changes = XWindowChanges()
        changes.sibling = c_ulong(target_xid)
        changes.stack_mode = 0  # Above
        # CWSibling (32) | CWStackMode (64) = 96
        self.x11.XConfigureWindow(self._display, c_ulong(window_xid), 96, byref(changes))
        self.x11.XFlush(self._display)

    def set_transient_for(self, window_xid: int, target_xid: int):
        if self._display and window_xid and target_xid:
            self.x11.XSetTransientForHint(self._display, c_ulong(window_xid), c_ulong(target_xid))
            self.x11.XFlush(self._display)
        return self._display is not None

    def get_client_windows(self) -> List[int]:
        """Returns client windows in bottom-to-top stacking order."""
        if not self._display:
            return []
        atom_client_list = self.x11.XInternAtom(self._display, b"_NET_CLIENT_LIST_STACKING", 0)
        atom_window = self.x11.XInternAtom(self._display, b"WINDOW", 0)
        actual_type = c_ulong()
        actual_format = c_int()
        nitems = c_ulong()
        bytes_after = c_ulong()
        prop = c_void_p()

        root = self.x11.XDefaultRootWindow(self._display)
        res = self.x11.XGetWindowProperty(
            self._display, root, atom_client_list,
            0, 4096, 0, atom_window,
            byref(actual_type), byref(actual_format),
            byref(nitems), byref(bytes_after), byref(prop)
        )
        if res != 0 or not prop.value:
            # Fallback to _NET_CLIENT_LIST
            atom_fallback = self.x11.XInternAtom(self._display, b"_NET_CLIENT_LIST", 0)
            res = self.x11.XGetWindowProperty(
                self._display, root, atom_fallback,
                0, 4096, 0, atom_window,
                byref(actual_type), byref(actual_format),
                byref(nitems), byref(bytes_after), byref(prop)
            )

        windows = []
        if res == 0 and prop.value:
            ulong_p = ctypes.cast(prop.value, POINTER(c_ulong))
            for i in range(nitems.value):
                windows.append(ulong_p[i])
            self.x11.XFree(prop.value)
        return windows

    def find_windows_by_pid(self, pid: int) -> List[int]:
        if not self._display or pid <= 0:
            return []
        matched = []
        for w in self.get_client_windows():
            if self.get_window_pid(w) == pid:
                matched.append(w)
        return matched

    def get_window_title(self, xid: int) -> str:
        if not self._display:
            return ""
        name_ptr = c_char_p()
        title = ""
        if self.x11.XFetchName(self._display, c_ulong(xid), byref(name_ptr)) and name_ptr.value:
            try:
                title = name_ptr.value.decode("utf-8", errors="replace")
            except Exception:
                pass
            self.x11.XFree(name_ptr)
            return title

        # Try _NET_WM_NAME
        atom_net_wm_name = self.x11.XInternAtom(self._display, b"_NET_WM_NAME", 0)
        atom_utf8_string = self.x11.XInternAtom(self._display, b"UTF8_STRING", 0)
        actual_type = c_ulong()
        actual_format = c_int()
        nitems = c_ulong()
        bytes_after = c_ulong()
        prop = c_void_p()

        res = self.x11.XGetWindowProperty(
            self._display, c_ulong(xid), atom_net_wm_name,
            0, 1024, 0, atom_utf8_string,
            byref(actual_type), byref(actual_format),
            byref(nitems), byref(bytes_after), byref(prop)
        )
        if res == 0 and prop.value:
            raw = ctypes.cast(prop.value, c_char_p).value
            if raw:
                title = raw.decode("utf-8", errors="replace")
            self.x11.XFree(prop.value)

        return title

    def get_window_pid(self, xid: int) -> int:
        if not self._display:
            return 0
        atom_pid = self.x11.XInternAtom(self._display, b"_NET_WM_PID", 0)
        atom_cardinal = self.x11.XInternAtom(self._display, b"CARDINAL", 0)
        actual_type = c_ulong()
        actual_format = c_int()
        nitems = c_ulong()
        bytes_after = c_ulong()
        prop = c_void_p()

        res = self.x11.XGetWindowProperty(
            self._display, c_ulong(xid), atom_pid,
            0, 1, 0, atom_cardinal,
            byref(actual_type), byref(actual_format),
            byref(nitems), byref(bytes_after), byref(prop)
        )
        pid = 0
        if res == 0 and prop.value:
            try:
                pid = ctypes.cast(prop.value, POINTER(c_ulong))[0]
            except Exception:
                pass
            self.x11.XFree(prop.value)
        return pid

    def get_window_geometry(self, xid: int) -> Optional[Tuple[int, int, int, int]]:
        """Returns (root_x, root_y, width, height) in root coordinates."""
        if not self._display:
            return None
        root_ret = c_ulong()
        x_ret = c_int()
        y_ret = c_int()
        w_ret = c_uint()
        h_ret = c_uint()
        b_ret = c_uint()
        d_ret = c_uint()

        res = self.x11.XGetGeometry(
            self._display, c_ulong(xid),
            byref(root_ret), byref(x_ret), byref(y_ret),
            byref(w_ret), byref(h_ret), byref(b_ret), byref(d_ret)
        )
        if res == 0:
            return None

        # Translate to root coordinates
        dest_x = c_int()
        dest_y = c_int()
        child = c_ulong()
        t_res = self.x11.XTranslateCoordinates(
            self._display, c_ulong(xid), root_ret.value,
            0, 0, byref(dest_x), byref(dest_y), byref(child)
        )
        if t_res == 0:
            return None

        return (dest_x.value, dest_y.value, w_ret.value, h_ret.value)

    def get_window_frame_extents(self, xid: int) -> Tuple[int, int, int, int]:
        """Returns (left, right, top, bottom) extents added by the window manager."""
        if not self._display:
            return (0, 0, 0, 0)
        atom_extents = self.x11.XInternAtom(self._display, b"_NET_FRAME_EXTENTS", 0)
        atom_cardinal = self.x11.XInternAtom(self._display, b"CARDINAL", 0)
        actual_type = c_ulong()
        actual_format = c_int()
        nitems = c_ulong()
        bytes_after = c_ulong()
        prop = c_void_p()

        res = self.x11.XGetWindowProperty(
            self._display, c_ulong(xid), atom_extents,
            0, 4, 0, atom_cardinal,
            byref(actual_type), byref(actual_format),
            byref(nitems), byref(bytes_after), byref(prop)
        )
        extents = (0, 0, 0, 0)
        if res == 0 and prop.value:
            if nitems.value >= 4:
                lp = ctypes.cast(prop.value, POINTER(c_ulong))
                extents = (int(lp[0]), int(lp[1]), int(lp[2]), int(lp[3]))
            self.x11.XFree(prop.value)
        return extents

    def get_window_gtk_frame_extents(self, xid: int) -> Tuple[int, int, int, int]:
        """Returns (left, right, top, bottom) invisible client-side decoration shadow extents."""
        if not self._display:
            return (0, 0, 0, 0)
        atom_extents = self.x11.XInternAtom(self._display, b"_GTK_FRAME_EXTENTS", 0)
        atom_cardinal = self.x11.XInternAtom(self._display, b"CARDINAL", 0)
        actual_type = c_ulong()
        actual_format = c_int()
        nitems = c_ulong()
        bytes_after = c_ulong()
        prop = c_void_p()

        res = self.x11.XGetWindowProperty(
            self._display, c_ulong(xid), atom_extents,
            0, 4, 0, atom_cardinal,
            byref(actual_type), byref(actual_format),
            byref(nitems), byref(bytes_after), byref(prop)
        )
        extents = (0, 0, 0, 0)
        if res == 0 and prop.value:
            if nitems.value >= 4:
                lp = ctypes.cast(prop.value, POINTER(c_ulong))
                extents = (int(lp[0]), int(lp[1]), int(lp[2]), int(lp[3]))
            self.x11.XFree(prop.value)
        return extents

    def get_full_window_geometry(self, xid: int) -> Optional[Tuple[int, int, int, int]]:
        """Returns (outer_x, outer_y, outer_w, outer_h) including titlebar and window frame, adjusting for CSD margins."""
        geom = self.get_window_geometry(xid)
        if not geom:
            return None
        x, y, w, h = geom
        left, right, top, bottom = self.get_window_frame_extents(xid)
        gtk_left, gtk_right, gtk_top, gtk_bottom = self.get_window_gtk_frame_extents(xid)

        fx = x - left + gtk_left
        fy = y - top + gtk_top
        fw = w + (left + right) - (gtk_left + gtk_right)
        fh = h + (top + bottom) - (gtk_top + gtk_bottom)
        return (fx, fy, max(1, fw), max(1, fh))

    def find_windows_by_title_pattern(self, pattern: str) -> List[Tuple[int, str]]:
        if not self._display:
            return []
        matches = []
        # Check all managed client windows first
        for w in self.get_client_windows():
            title = self.get_window_title(w)
            if pattern.lower() in title.lower():
                matches.append((w, title))

        if matches:
            return matches

        root = self.x11.XDefaultRootWindow(self._display)
        root_ret = c_ulong()
        parent_ret = c_ulong()
        children_ret = POINTER(c_ulong)()
        nchildren = c_uint()

        status = self.x11.XQueryTree(
            self._display, root,
            byref(root_ret), byref(parent_ret),
            byref(children_ret), byref(nchildren)
        )
        if status != 0 and children_ret:
            for i in range(nchildren.value):
                w = children_ret[i]
                title = self.get_window_title(w)
                if pattern.lower() in title.lower():
                    matches.append((w, title))
            self.x11.XFree(children_ret)
        return matches

    def close(self):
        if self._display:
            self.x11.XCloseDisplay(self._display)
            self._display = None
