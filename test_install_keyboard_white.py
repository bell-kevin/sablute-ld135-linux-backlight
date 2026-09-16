# SPDX-License-Identifier: AGPL-3.0-only
"""Test installation in temporary directories without changing the host."""

import contextlib
import io
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import install_keyboard_white as installer


class InstallerTests(unittest.TestCase):
    def setUp(self):
        previous_umask = os.umask(0o022)
        self.addCleanup(os.umask, previous_umask)
        self.temporary = tempfile.TemporaryDirectory(prefix="ld135 installer ")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / "source with spaces"
        self.source.mkdir()
        for name in (*installer.SYSTEM_FILES, installer.DESKTOP_FILE,
                     "install_keyboard_white.py"):
            shutil.copyfile(installer.SOURCE / name, self.source / name)
        self.stage = self.base / "staging with spaces"
        self.source_patch = patch.object(installer, "SOURCE", self.source)
        self.source_patch.start()
        self.addCleanup(self.source_patch.stop)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def system(self, action, dry_run=False):
        with patch.object(installer, "refresh_udev") as refresh:
            installer.system_operation(action, str(self.stage), dry_run)
            refresh.assert_not_called()

    def target(self, name):
        return self.stage / installer.SYSTEM_FILES[name][0]

    def test_install_update_and_uninstall_only_known_files(self):
        self.system("install")
        targets = [self.target(name) for name in installer.SYSTEM_FILES]
        self.assertEqual(sorted(p for p in self.stage.rglob("*") if p.is_file()),
                         sorted(targets))
        for name, (_, mode) in installer.SYSTEM_FILES.items():
            target = self.target(name)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), mode)
            self.assertEqual(target.stat().st_uid, os.geteuid())
            self.assertIn(installer.marker(name), target.read_bytes().splitlines(keepends=True)[:2])
        untouched = self.stage / "keep.txt"
        untouched.write_text("unrelated")
        script = self.source / "keyboard_white.py"
        script.write_bytes(script.read_bytes() + b"\n# Updated release\n")
        self.system("install")
        self.assertTrue(self.target("keyboard_white.py").read_bytes().endswith(b"# Updated release\n"))
        self.system("uninstall")
        self.system("uninstall")
        self.assertTrue(untouched.is_file())
        self.assertTrue(all(not target.exists() for target in targets))

    def test_dry_run_makes_no_directories_or_changes(self):
        self.system("install", dry_run=True)
        self.assertFalse(self.stage.exists())
        self.system("install")
        before = self.target("keyboard_white.py").read_bytes()
        self.system("uninstall", dry_run=True)
        self.assertEqual(self.target("keyboard_white.py").read_bytes(), before)

    def test_installer_locates_source_from_another_working_directory(self):
        result = subprocess.run(
            [sys.executable, str(self.source / "install_keyboard_white.py"),
             "--system", "install", "--destdir", str(self.stage)],
            cwd=self.base, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.target("ld135-white").is_file())

    def test_unrelated_file_aborts_before_installing_anything(self):
        target = self.target("70-ld135-white.rules")
        target.parent.mkdir(parents=True)
        target.write_text("another project's rule\n")
        target.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, "unrelated"):
            self.system("install")
        self.assertFalse(self.target("keyboard_white.py").exists())
        self.assertEqual(target.read_text(), "another project's rule\n")

    def test_unrelated_file_aborts_before_uninstalling_anything(self):
        self.system("install")
        target = self.target("70-ld135-white.rules")
        target.write_text("another project's rule\n")
        with self.assertRaisesRegex(RuntimeError, "unrelated"):
            self.system("uninstall")
        self.assertTrue(self.target("keyboard_white.py").is_file())

    def test_target_symlink_is_never_replaced_or_deleted(self):
        other = self.base / "other.py"
        other.write_text("preserve")
        target = self.target("keyboard_white.py")
        target.parent.mkdir(parents=True)
        target.symlink_to(other)
        for action in ("install", "uninstall"):
            with self.assertRaisesRegex(RuntimeError, "symlink"):
                self.system(action)
        self.assertTrue(target.is_symlink())
        self.assertEqual(other.read_text(), "preserve")

    def test_symlink_parent_is_rejected(self):
        self.stage.mkdir()
        other = self.base / "other"
        other.mkdir()
        (self.stage / "usr").symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            self.system("install")
        self.assertEqual(list(other.iterdir()), [])

    def test_source_symlink_is_rejected_before_writes(self):
        source = self.source / "70-ld135-white.rules"
        other = self.base / "other.rules"
        source.rename(other)
        source.symlink_to(other)
        with self.assertRaisesRegex(RuntimeError, "Source must be"):
            self.system("install")
        self.assertFalse(self.stage.exists())

    def test_missing_source_is_rejected_before_writes(self):
        (self.source / "70-ld135-white.rules").unlink()
        with self.assertRaises(FileNotFoundError):
            self.system("install")
        self.assertFalse(self.stage.exists())

    def test_unsafe_directory_permissions_are_rejected(self):
        self.stage.mkdir()
        self.stage.chmod(0o777)
        with self.assertRaisesRegex(RuntimeError, "Directory must be"):
            self.system("install")

    def test_unexpected_file_permissions_are_rejected(self):
        self.system("install")
        self.target("ld135-white").chmod(0o777)
        with self.assertRaisesRegex(RuntimeError, "permissions"):
            self.system("install")

    def test_unexpected_file_owner_is_rejected(self):
        self.system("install")
        with self.assertRaisesRegex(RuntimeError, "ownership"):
            installer.existing_payload(self.target("ld135-white"), "ld135-white",
                                       0o755, os.geteuid() + 1)

    def test_hard_link_destination_is_rejected(self):
        self.system("install")
        target = self.target("ld135-white")
        linked = self.base / "linked wrapper"
        os.link(target, linked)
        with self.assertRaisesRegex(RuntimeError, "hard link"):
            self.system("uninstall")
        self.assertTrue(linked.is_file())

    def test_restrictive_umask_does_not_make_program_inaccessible(self):
        previous = os.umask(0o077)
        try:
            self.system("install")
        finally:
            os.umask(previous)
        for path in self.stage.rglob("*"):
            if path.is_dir():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o755)

    def test_original_unmarked_wrapper_can_be_upgraded(self):
        target = self.target("ld135-white")
        target.parent.mkdir(parents=True)
        target.write_bytes(b'#!/bin/sh\nexec /usr/bin/python3 -I /usr/local/lib/ld135-white/keyboard_white.py "$@"\n')
        target.chmod(0o755)
        self.system("install")
        self.assertIn(installer.marker("ld135-white"), target.read_bytes())

    def test_real_system_change_requires_root(self):
        with patch.object(installer.os, "geteuid", return_value=1234), \
                patch.object(installer, "apply_files") as apply_files:
            with self.assertRaisesRegex(RuntimeError, "requires sudo"):
                installer.system_operation("install")
        apply_files.assert_not_called()

    def test_destdir_root_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "not /"):
            installer.system_operation("install", "/")

    def test_autostart_uses_xdg_config_and_can_be_disabled(self):
        config = self.base / "chosen config"
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}), \
                patch.object(installer, "require_regular_user", return_value=os.geteuid()):
            installer.autostart_operation("enable")
            desktop = config / "autostart" / installer.DESKTOP_FILE
            self.assertIn(b"Exec=/usr/local/bin/ld135-white --wait 30", desktop.read_bytes())
            self.assertEqual(stat.S_IMODE(desktop.stat().st_mode), 0o644)
            installer.autostart_operation("enable")
            installer.autostart_operation("disable")
            self.assertFalse(desktop.exists())

    def test_autostart_defaults_to_current_users_home(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "", "HOME": str(self.base)}), \
                patch.object(installer, "require_regular_user", return_value=os.geteuid()):
            installer.autostart_operation("enable")
        self.assertTrue((self.base / ".config/autostart/ld135-white.desktop").is_file())

    def test_autostart_rejects_root(self):
        with patch.object(installer.os, "geteuid", return_value=0), \
                patch.object(installer, "apply_files") as apply_files:
            with self.assertRaisesRegex(RuntimeError, "regular desktop user"):
                installer.autostart_operation("enable")
        apply_files.assert_not_called()

    def test_autostart_rejects_relative_xdg_config(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "relative"}), \
                patch.object(installer, "require_regular_user", return_value=os.geteuid()):
            with self.assertRaisesRegex(RuntimeError, "absolute"):
                installer.autostart_operation("enable")

    def test_autostart_dry_run_has_no_side_effects(self):
        config = self.base / "chosen config"
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}), \
                patch.object(installer, "require_regular_user", return_value=os.geteuid()):
            installer.autostart_operation("enable", dry_run=True)
        self.assertFalse(config.exists())


if __name__ == "__main__":
    unittest.main()
