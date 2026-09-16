#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Install/update or remove the LD-135 helper, and manage per-user autostart.

System changes require root, except --destdir staging or --dry-run. Autostart
changes must run as the regular desktop user. This installer never sets a color.
"""

import argparse
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile


SOURCE = Path(__file__).resolve().parent
SYSTEM_FILES = {
    "keyboard_white.py": ("usr/local/lib/ld135-white/keyboard_white.py", 0o644),
    "ld135-white": ("usr/local/bin/ld135-white", 0o755),
    "70-ld135-white.rules": ("etc/udev/rules.d/70-ld135-white.rules", 0o644),
}
DESKTOP_FILE = "ld135-white.desktop"
PROJECT = "sablute-ld135-linux-backlight"
# Recognize only the exact files from the original private installation when
# migrating it to a managed release. Source files no longer need pinned hashes.
LEGACY_HASHES = {
    "keyboard_white.py": {"d168d95666791d2f7cfe4201e33e9a72df5b39d9cd05e97068c21c0dc1f3f86d"},
    "ld135-white": {"55b1ec7bfb5ac71b919823ae34cea60042eb593314b7fbb55614351bf044f55d"},
    "70-ld135-white.rules": {"951cae06b033eca13d82a862b1a82e7909c160f039b5466dae27585bc9c7ae9d"},
}
LEGACY_DESKTOP = b"""[Desktop Entry]
Type=Application
Version=1.0
Name=White keyboard at login
Comment=Set the SABLUTE keyboard to white once when you sign in
Exec=/usr/local/bin/ld135-white --wait 30
TryExec=/usr/local/bin/ld135-white
Terminal=false
X-GNOME-Autostart-enabled=true
"""
LEGACY_HASHES[DESKTOP_FILE] = {hashlib.sha256(LEGACY_DESKTOP).hexdigest()}


def marker(name):
    return f"# Managed by {PROJECT}: {name}\n".encode()


def source_payload(name):
    path = SOURCE / name
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f"Source must be a regular file, not a symlink: {path}")
    data = path.read_bytes()
    if not data or b"\0" in data:
        raise RuntimeError(f"Invalid text source: {path}")
    if data.startswith(b"#!"):
        first, separator, rest = data.partition(b"\n")
        return first + separator + marker(name) + rest
    return marker(name) + data


def check_no_symlinks(path):
    """Check existing components without resolving away symlinks."""
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise RuntimeError(f"Refusing a symlink in the installation path: {component}")


def check_directories(root, parent, owner):
    check_no_symlinks(parent)
    relative = parent.relative_to(root)
    components = [root]
    for part in relative.parts:
        components.append(components[-1] / part)
    for directory in components:
        try:
            info = directory.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != owner or info.st_mode & 0o022:
            raise RuntimeError(f"Directory must be owned and writable only by the installing user: {directory}")


def existing_payload(path, name, mode, owner):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RuntimeError(f"Refusing a symlink, hard link, or non-file destination: {path}")
    if info.st_uid != owner or stat.S_IMODE(info.st_mode) != mode:
        raise RuntimeError(f"Unexpected ownership or permissions: {path}")
    data = path.read_bytes()
    first_lines = data.splitlines(keepends=True)[:2]
    managed = marker(name) in first_lines
    legacy = hashlib.sha256(data).hexdigest() in LEGACY_HASHES.get(name, set())
    if not managed and not legacy:
        raise RuntimeError(f"Refusing to overwrite or remove an unrelated file: {path}")
    return data


def atomic_write(path, data, mode):
    fd, temporary = tempfile.mkstemp(prefix=".ld135-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply_files(root, specifications, install, owner, dry_run):
    # Validate every source/destination before writing or deleting any target.
    planned = []
    for name, (relative, mode) in specifications.items():
        path = root / relative
        check_directories(root, path.parent, owner)
        previous = existing_payload(path, name, mode, owner)
        desired = source_payload(name) if install else None
        planned.append((name, path, mode, previous, desired))
    for name, path, mode, previous, desired in planned:
        if previous == desired:
            print(f"Unchanged: {path}")
            continue
        action = "Install/update" if install else "Remove"
        print(f"{'Would ' if dry_run else ''}{action}: {path}")
        if dry_run:
            continue
        check_directories(root, path.parent, owner)
        if existing_payload(path, name, mode, owner) != previous:
            raise RuntimeError(f"Destination changed during installation: {path}")
        if install:
            previous_umask = os.umask(0o022)
            try:
                path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            finally:
                os.umask(previous_umask)
            atomic_write(path, desired, mode)
        else:
            path.unlink()


def refresh_udev():
    command = "/usr/bin/udevadm"
    subprocess.run([command, "control", "--reload-rules"], check=True, timeout=10)
    for entry in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        try:
            properties = (entry / "device/uevent").read_text().splitlines()
        except FileNotFoundError:
            continue
        if "HID_ID=0003:000030FA:00002052" in properties:
            subprocess.run([command, "trigger", "--action=change", str(entry)],
                           check=True, timeout=10)
    subprocess.run([command, "settle", "--timeout=5"], check=True, timeout=10)


def system_operation(action, destdir=None, dry_run=False):
    if destdir is None:
        root, owner = Path("/"), 0
        if os.geteuid() != 0 and not dry_run:
            raise RuntimeError("System installation/removal requires sudo or pkexec.")
        if not dry_run and not Path("/usr/bin/udevadm").is_file():
            raise RuntimeError("This installation requires /usr/bin/udevadm.")
    else:
        root = Path(os.path.abspath(os.path.expanduser(destdir)))
        if root == Path("/"):
            raise RuntimeError("--destdir must be a staging directory, not /.")
        owner = os.geteuid()
        check_no_symlinks(root)
    apply_files(root, SYSTEM_FILES, action == "install", owner, dry_run)
    if destdir is None and not dry_run:
        refresh_udev()
    if action == "uninstall":
        print("Disable autostart separately as each desktop user, if enabled.")


def require_regular_user():
    if os.geteuid() == 0 or os.getuid() == 0:
        raise RuntimeError("Run --autostart as your regular desktop user, without sudo or pkexec.")
    return os.geteuid()


def autostart_operation(action, dry_run=False):
    owner = require_regular_user()
    configured = os.environ.get("XDG_CONFIG_HOME")
    root = Path(configured) if configured else Path.home() / ".config"
    if not root.is_absolute():
        raise RuntimeError("XDG_CONFIG_HOME must be an absolute path.")
    specifications = {DESKTOP_FILE: (f"autostart/{DESKTOP_FILE}", 0o644)}
    apply_files(root, specifications, action == "enable", owner, dry_run)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--system", choices=("install", "uninstall"),
                           help="Install/update or remove the three system files.")
    operation.add_argument("--autostart", choices=("enable", "disable"),
                           help="Enable or disable white at graphical login for this user.")
    parser.add_argument("--dry-run", action="store_true", help="Check and preview without changing files.")
    parser.add_argument("--destdir", metavar="PATH",
                        help="Stage --system files below PATH; no root requirement or udev changes.")
    args = parser.parse_args(argv)
    if args.destdir is not None and args.autostart:
        parser.error("--destdir is only available with --system")
    if args.system:
        system_operation(args.system, args.destdir, args.dry_run)
    else:
        autostart_operation(args.autostart, args.dry_run)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"LD-135 installer: {error}", file=sys.stderr)
        sys.exit(1)
