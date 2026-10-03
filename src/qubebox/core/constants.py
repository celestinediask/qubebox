"""QubeBox Constants and Theme Definitions."""

import os
from pathlib import Path

# Paths
APP_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RUNTIME_DIR = APP_ROOT / "runtime"
VMS_DIR = APP_ROOT / "vms"
ICONS_DIR = APP_ROOT / "icons"

# Qubes-style Security Colors
QUBES_COLORS = [
    {"name": "Red", "hex": "#e74c3c", "tag": "untrusted", "desc": "Untrusted / Risky / Disposable"},
    {"name": "Orange", "hex": "#e67e22", "tag": "untrusted", "desc": "Semi-trusted / Testing"},
    {"name": "Yellow", "hex": "#f1c40f", "tag": "semi-trusted", "desc": "Personal / Casual"},
    {"name": "Green", "hex": "#2ecc71", "tag": "trusted", "desc": "Work / Safe"},
    {"name": "Blue", "hex": "#3498db", "tag": "trusted", "desc": "Development / Code"},
    {"name": "Purple", "hex": "#9b59b6", "tag": "vault", "desc": "Finance / Banking"},
    {"name": "Gray", "hex": "#7f8c8d", "tag": "template", "desc": "Templates & Base Images"},
    {"name": "Black", "hex": "#2c3e50", "tag": "dom0", "desc": "System / Admin / Secure"},
]

COLOR_MAP = {c["name"]: c["hex"] for c in QUBES_COLORS}
COLOR_NAME_MAP = {c["hex"].lower(): c["name"] for c in QUBES_COLORS}

# VM Types
VM_TYPE_APPVM = "AppVM"
VM_TYPE_TEMPLATEVM = "TemplateVM"
VM_TYPE_STANDALONEVM = "StandaloneVM"
VM_TYPE_DISPVM = "DispVM"

VM_TYPES = [
    VM_TYPE_APPVM,
    VM_TYPE_TEMPLATEVM,
    VM_TYPE_STANDALONEVM,
    VM_TYPE_DISPVM
]

# Network Modes
NET_MODE_DEFAULT = "default"  # User mode NAT (Slirp)
NET_MODE_NONE = "none"        # Air-gapped / Vault (no network)
NET_MODE_RESTRICTED = "isolated" # Restrict outbound access

# Seamless window modes
DISPLAY_SEAMLESS = "seamless"
DISPLAY_WINDOW = "window"
DISPLAY_HEADLESS = "headless"
