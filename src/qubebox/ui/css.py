"""Dark theme CSS stylesheet for QubeBox."""

DARK_THEME_CSS = """
/* Global Dark Theme Settings */
* {
    color: #e0e0e0;
}

window, dialog {
    background-color: #1e1e24;
}

/* Lightweight Classic Top Toolbar */
.classic-toolbar {
    background-color: #17171d;
    padding: 4px 12px;
}

button.toolbar-icon-btn,
button.toolbar-icon-btn:active,
button.toolbar-icon-btn:focus {
    background: transparent;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 3px 5px;
    color: #8c8fa8;
    box-shadow: none;
}

button.toolbar-icon-btn image {
    color: #8c8fa8;
}

button.toolbar-icon-btn:hover {
    background: transparent;
    border-color: transparent;
    color: #ffffff;
}

button.toolbar-icon-btn:hover image {
    color: #ffffff;
}

/* Action Icon Buttons in Table Rows */
button.action-btn,
button.action-btn:active,
button.action-btn:focus {
    background: transparent;
    background-color: transparent;
    background-image: none;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 3px 5px;
    color: #8c8fa8;
    box-shadow: none;
}

button.action-btn image {
    color: #8c8fa8;
}

button.action-btn:hover {
    background: transparent;
    border-color: transparent;
    color: #ffffff;
}

button.action-btn:hover image {
    color: #ffffff;
}

/* Distinct hover accents for each action button - icon highlights, NOT background */
button.action-btn-green:hover image {
    color: #2ecc71;
}

button.action-btn-pause:hover image {
    color: #3498db;
}

button.action-btn-yellow:hover image {
    color: #f1c40f;
}

button.action-btn-blue:hover image {
    color: #3498db;
}

button.action-btn-red:hover image {
    color: #e74c3c;
}

button.action-btn:disabled {
    background: transparent;
    border-color: transparent;
    color: #63677e;
    opacity: 0.65;
}

button.action-btn:disabled image {
    color: #63677e;
    opacity: 0.65;
}

/* Clean Type Labels (no fancy background box) */
.type-label {
    font-weight: 500;
    color: #c5c7d8;
    padding: 0;
    background: transparent;
    border: none;
}

/* Table Header Labels */
label.th-label {
    font-weight: bold;
    font-size: 11px;
    color: #8f90a6;
    letter-spacing: 0.5px;
}

/* Card Boxes & Dialogs */
.card-box {
    background-color: #22222a;
    border: 1px solid #2e2e38;
    border-radius: 8px;
    padding: 14px;
    margin: 8px;
}

/* Compact input fields */
entry {
    background-color: #16161a;
    border: 1px solid #3c3d4a;
    color: #ffffff;
    border-radius: 4px;
    padding: 3px 8px;
    min-height: 26px;
}

entry:focus {
    border-color: #3498db;
}

combobox button {
    background-color: #16161a;
    border: 1px solid #3c3d4a;
    color: #ffffff;
    border-radius: 4px;
    padding: 2px 8px;
    min-height: 26px;
}

combobox button:focus {
    border-color: #3498db;
}

/* SpinButton: clean single-container styling, no nested borders or bloated padding */
spinbutton {
    background-color: #16161a;
    border: 1px solid #3c3d4a;
    border-radius: 4px;
    padding: 0;
    min-height: 26px;
}

spinbutton:focus,
spinbutton:focus-within {
    border-color: #3498db;
}

spinbutton entry {
    background: transparent;
    background-color: transparent;
    border: none;
    box-shadow: none;
    color: #ffffff;
    padding: 2px 6px;
    min-height: 24px;
}

spinbutton button {
    background: transparent;
    background-color: transparent;
    border: none;
    box-shadow: none;
    color: #8c8fa8;
    padding: 2px 6px;
    min-height: 24px;
}

spinbutton button:hover {
    color: #ffffff;
    background-color: #2b2c3c;
}

spinbutton button:active {
    color: #ffffff;
    background-color: #36374a;
}

/* App Launcher Popover Menu */
popover, popover.background {
    background-color: #1a1a22;
    border: 1px solid #363748;
    border-radius: 8px;
    padding: 6px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
}

button.app-menu-item {
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
    color: #e0e0e0;
}

button.app-menu-item:hover {
    background-color: #2b2c3c;
    color: #ffffff;
}

button.app-menu-item image {
    color: #3498db;
    margin-right: 8px;
}

label.subtitle {
    color: #8f90a6;
    font-size: 11px;
}

/* Settings & Clean Slate Dialog Styling */
button.btn-destructive {
    background-color: #c0392b;
    border: 1px solid #e74c3c;
    color: #ffffff;
    font-weight: bold;
    border-radius: 4px;
    padding: 5px 14px;
}

button.btn-destructive:hover {
    background-color: #e74c3c;
    color: #ffffff;
}

.settings-dialog checkbutton {
    font-size: 13px;
    padding: 2px 0px;
    color: #e0e0e0;
}
"""


