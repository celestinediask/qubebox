# QubeBox

**QubeBox** is a lightweight, rootless GUI virtual machine manager for Linux inspired by **Qubes OS**. It provides compartmentalized security domains, instant disposable VMs, and color-coded security borders without requiring system daemons or root privileges.

---

## Features

- **Security Domains**:
  - **AppVMs**: Persistent user storage (`/rw`) layered over an immutable TemplateVM root image. System changes discard upon reboot.
  - **DispVMs (Disposable)**: Ephemeral VMs that automatically wipe all disk changes upon shutdown.
  - **TemplateVMs**: Clean base operating system templates.
  - **StandaloneVMs**: Fully independent virtual machines.
- **Color-Coded Security Borders**: Visual indicators (Red, Green, Blue, Yellow, Orange, Purple, Gray, Black) with transparent window overlays.
- **Rootless & Daemonless**: Runs standard user-space QEMU with user-mode networking (`slirp`) or air-gapped vault mode (`none`). No `libvirtd` or `sudo` required.
- **Dark Theme UI**: Clean, responsive GTK3 interface.

---

## Requirements

Ensure the following packages are installed on your Linux system:

- Python 3.10+
- GTK 3 & PyGObject (`python3-gi`, `gir1.2-gtk-3.0`)
- QEMU (`qemu-system-x86`, `qemu-utils`)
- KVM (optional, for hardware virtualization acceleration)

## Getting Started

### 1. Launch QubeBox

Run the launcher script:
```bash
./qubebox
```

## License

Open source under the [MIT License](LICENSE).
