# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 bell-kevin
"""Hardware-free tests for the narrowly scoped lighting controller."""

import errno
import struct
import unittest
from unittest.mock import patch

import keyboard_white as controller


class LightingTests(unittest.TestCase):
    def setUp(self):
        self.before = bytes.fromhex("07 00 c1 40 41 41 02 12")
        self.white = bytes.fromhex("07 00 c1 40 41 41 02 72")

    def test_one_write_preserves_brightness_and_other_channel(self):
        before = self.before[:4] + bytes([0x19]) + self.before[5:]
        after = before[:7] + bytes([0x72])
        with patch.object(controller, "stable_status", return_value=before), \
                patch.object(controller, "read_status", return_value=after), \
                patch.object(controller, "hid_ioctl", return_value=8) as transport, \
                patch.object(controller.time, "sleep"):
            controller.set_white(12)
        transport.assert_called_once_with(
            12, controller.HIDIOCSFEATURE_8, bytearray.fromhex("07 13 00 00 19 72 ff ff"))

    def test_already_white_never_writes(self):
        with patch.object(controller, "stable_status", return_value=self.white), \
                patch.object(controller, "hid_ioctl") as transport:
            controller.set_white(12)
        transport.assert_not_called()

    def test_failed_verification_does_not_repeat_write(self):
        with patch.object(controller, "stable_status", return_value=self.before), \
                patch.object(controller, "read_status", return_value=self.before), \
                patch.object(controller, "hid_ioctl", return_value=8) as transport, \
                patch.object(controller.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "no retry"):
                controller.set_white(12)
        self.assertEqual(transport.call_count, 1)

    def test_unexpected_other_channel_change_fails_verification(self):
        after = bytearray(self.white)
        after[5] = 0x11
        with patch.object(controller, "stable_status", return_value=self.before), \
                patch.object(controller, "read_status", return_value=after), \
                patch.object(controller, "hid_ioctl", return_value=8) as transport, \
                patch.object(controller.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "could not be verified"):
                controller.set_white(12)
        self.assertEqual(transport.call_count, 1)

    def test_write_failure_has_no_second_write(self):
        with patch.object(controller, "stable_status", return_value=self.before), \
                patch.object(controller, "hid_ioctl", side_effect=OSError("USB error")) as transport:
            with self.assertRaises(OSError):
                controller.set_white(12)
        self.assertEqual(transport.call_count, 1)

    def test_fn_is_released_before_stable_baseline(self):
        held = bytearray(self.before)
        held[2] = 0x81
        with patch.object(controller, "read_status", side_effect=[held, self.before, self.before]), \
                patch.object(controller.time, "sleep"):
            self.assertEqual(controller.stable_status(12), self.before)

    def test_held_fn_timeout_does_not_write(self):
        held = bytearray(self.before)
        held[2] = 0x81
        with patch.object(controller, "read_status", return_value=held), \
                patch.object(controller.time, "monotonic", side_effect=[0, 4]), \
                patch.object(controller, "hid_ioctl") as transport:
            with self.assertRaisesRegex(RuntimeError, "Fn is held"):
                controller.set_white(12)
        transport.assert_not_called()

    def test_non_normal_status_rejected_before_write(self):
        requests = []

        def transport(_fd, request, data):
            requests.append(request)
            data[:] = bytes.fromhex("07 18 c1 40 41 41 02 12")
            return 8

        with patch.object(controller, "hid_ioctl", side_effect=transport):
            with self.assertRaisesRegex(RuntimeError, "Unexpected keyboard status"):
                controller.set_white(12)
        self.assertEqual(requests, [controller.HIDIOCGFEATURE_8])

    def test_wrong_open_device_closes_without_feature_write(self):
        requests = []

        def transport(_fd, request, data):
            requests.append(request)
            data[:] = struct.pack("=IHH", 3, 0x1234, 0x2052)
            return 0

        with patch.object(controller.os, "open", return_value=12), \
                patch.object(controller.os, "close") as close, \
                patch.object(controller, "hid_ioctl", side_effect=transport):
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                controller.open_device("/dev/hidraw-test")
        close.assert_called_once_with(12)
        self.assertEqual(requests, [controller.HIDIOCGRAWINFO])

    def test_wrong_interface_descriptor_closes_without_feature_write(self):
        requests = []

        def transport(_fd, request, data):
            requests.append(request)
            if request == controller.HIDIOCGRAWINFO:
                data[:] = struct.pack("=IHH", 3, 0x30FA, 0x2052)
            elif request == controller.HIDIOCGRDESCSIZE:
                data[:] = struct.pack("=I", 3)
            elif request == controller.HIDIOCGRDESC:
                data[4:7] = b"bad"
            return 0

        with patch.object(controller.os, "open", return_value=12), \
                patch.object(controller.os, "close") as close, \
                patch.object(controller, "hid_ioctl", side_effect=transport):
            with self.assertRaisesRegex(RuntimeError, "descriptor"):
                controller.open_device("/dev/hidraw-test")
        close.assert_called_once_with(12)
        self.assertNotIn(controller.HIDIOCSFEATURE_8, requests)

    def test_dry_run_never_opens_a_device(self):
        with patch.object(controller, "find_device", return_value="/dev/hidraw-test"), \
                patch.object(controller, "open_device") as open_device:
            self.assertEqual(controller.wait_for_device(0, dry_run=True),
                             ("/dev/hidraw-test", None))
        open_device.assert_not_called()

    def test_wait_retries_permissions_only_before_setting(self):
        with patch.object(controller, "find_device", return_value="/dev/hidraw-test"), \
                patch.object(controller, "open_device", side_effect=[
                    PermissionError(errno.EACCES, "denied"), 12]) as open_device, \
                patch.object(controller.time, "sleep"):
            self.assertEqual(controller.wait_for_device(1), ("/dev/hidraw-test", 12))
        self.assertEqual(open_device.call_count, 2)


if __name__ == "__main__":
    unittest.main()
