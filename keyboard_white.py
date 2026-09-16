#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 bell-kevin
# Project: sablute-ld135-linux-backlight
"""Set this SABLUTE LD-135 keyboard to steady white once, then exit.

Uses the tested Instant runtime lighting command only. Brightness and speed
are preserved. Later changes made with the keyboard's Fn keys remain in effect
until the next invocation. No key events, EEPROM, or firmware are accessed.
"""

import argparse
import errno
import fcntl
import hashlib
import os
from pathlib import Path
import signal
import struct
import sys
import time


HID_ID = "0003:000030FA:00002052"
DESCRIPTOR_SHA256 = "fc4de9961c5a701ba6f2aa806c0d85a6478104e1864fef2d0020cf5c7c093c48"
# Linux x86_64 hidraw ioctl definitions.
HIDIOCGRAWINFO = 0x80084803
HIDIOCGRDESCSIZE = 0x80044801
HIDIOCGRDESC = 0x90044802
HIDIOCGFEATURE_8 = 0xC0084807
HIDIOCSFEATURE_8 = 0xC0084806
WHITE_MODE = 0x72
FN_RELEASED_BIT = 0x40


class DeviceUnavailable(RuntimeError):
    """The exact keyboard interface has not appeared yet."""


def timed_out(_signum, _frame):
    raise TimeoutError("The keyboard did not answer within 10 seconds.")


def hid_ioctl(fd, request, data):
    signal.alarm(10)
    try:
        return fcntl.ioctl(fd, request, data, True)
    finally:
        signal.alarm(0)


def find_device():
    matches = []
    for entry in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        device = entry / "device"
        try:
            props = dict(line.split("=", 1) for line in
                         (device / "uevent").read_text().splitlines() if "=" in line)
            if props.get("HID_ID") != HID_ID:
                continue
            descriptor = (device / "report_descriptor").read_bytes()
            if hashlib.sha256(descriptor).hexdigest() == DESCRIPTOR_SHA256:
                matches.append(Path("/dev") / entry.name)
        except FileNotFoundError:
            continue
    if not matches:
        raise DeviceUnavailable("The matching LD-135 keyboard interface is not available.")
    if len(matches) != 1:
        raise RuntimeError("More than one matching LD-135 is connected; no setting changed.")
    return matches[0]


def verify_handle(fd):
    """Recheck both device and interface after opening, closing enumeration races."""
    info = bytearray(8)
    hid_ioctl(fd, HIDIOCGRAWINFO, info)
    if struct.unpack("=IHH", info) != (3, 0x30FA, 0x2052):
        raise RuntimeError("The open device does not match the LD-135.")
    size = bytearray(4)
    hid_ioctl(fd, HIDIOCGRDESCSIZE, size)
    length, = struct.unpack("=I", size)
    if not 1 <= length <= 4096:
        raise RuntimeError("The keyboard returned an unexpected descriptor size.")
    descriptor = bytearray(struct.pack("=I", length) + bytes(4096))
    hid_ioctl(fd, HIDIOCGRDESC, descriptor)
    returned_length, = struct.unpack("=I", descriptor[:4])
    if returned_length != length or hashlib.sha256(
            descriptor[4:4 + length]).hexdigest() != DESCRIPTOR_SHA256:
        raise RuntimeError("The open interface does not match the tested LD-135 descriptor.")


def open_device(path, read_only=False):
    flags = os.O_RDONLY if read_only else os.O_RDWR
    fd = os.open(path, flags | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        verify_handle(fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BaseException:
        os.close(fd)
        raise


def wait_for_device(wait_seconds, read_only=False, dry_run=False):
    """Retry only discovery/opening. Never retry a lighting write."""
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            path = find_device()
            return path, None if dry_run else open_device(path, read_only)
        except (DeviceUnavailable, OSError) as error:
            if isinstance(error, OSError) and error.errno not in (
                    errno.ENOENT, errno.ENODEV, errno.EACCES, errno.EPERM):
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            time.sleep(min(0.25, remaining))


def read_status(fd):
    report = bytearray([7] + [0] * 7)
    count = hid_ioctl(fd, HIDIOCGFEATURE_8, report)
    if count != 8 or report[0] != 7 or report[1] != 0:
        raise RuntimeError(f"Unexpected keyboard status: length={count}, "
                           f"data={report.hex(' ')}")
    return bytes(report)


def stable_status(fd, settle_seconds=3.0):
    """Allow a held Fn key or an in-progress manual color change to settle."""
    deadline = time.monotonic() + settle_seconds
    previous = None
    while True:
        current = read_status(fd)
        if current[2] & FN_RELEASED_BIT and current == previous:
            return current
        previous = current if current[2] & FN_RELEASED_BIT else None
        if time.monotonic() >= deadline:
            raise RuntimeError("The keyboard is still changing or Fn is held; no setting changed.")
        time.sleep(0.15)


def set_white(fd):
    before = stable_status(fd)
    if before[7] == WHITE_MODE:
        return "The keyboard is already steady white."
    # Locally verified: command[4] maps to GET[4], command[5] to GET[7].
    # Keep the vendor's ff ff trailer; its full meaning is not established.
    packet = bytearray([7, 0x13, 0, 0, before[4], WHITE_MODE, 0xFF, 0xFF])
    count = hid_ioctl(fd, HIDIOCSFEATURE_8, packet)
    if count != len(packet):
        raise RuntimeError(f"Unexpected lighting write result: {count}; no retry sent.")
    time.sleep(0.1)
    after = read_status(fd)
    if after[4:7] != before[4:7] or after[7] != WHITE_MODE:
        raise RuntimeError("White could not be verified after the single lighting command: "
                           f"{after.hex(' ')}; no retry sent.")
    return "The keyboard is steady white; brightness and speed were preserved."


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--status", action="store_true",
                        help="Read the current lighting status without changing it.")
    action.add_argument("--dry-run", action="store_true",
                        help="Identify the exact interface without opening or changing it.")
    parser.add_argument("--wait", type=int, default=0, metavar="SECONDS",
                        help="Wait 0 to 60 seconds for the device and permissions (default: 0).")
    args = parser.parse_args(argv)
    if not 0 <= args.wait <= 60:
        parser.error("--wait must be between 0 and 60 seconds")
    signal.signal(signal.SIGALRM, timed_out)
    path, fd = wait_for_device(args.wait, args.status, args.dry_run)
    if args.dry_run:
        print(f"Matched LD-135 interface: {path}")
        print("Would read its state and send at most one runtime command: "
              "07 13 00 00 <current brightness/speed> 72 ff ff")
        return 0
    try:
        if args.status:
            report = read_status(fd)
            description = "steady white" if report[7] == WHITE_MODE else "another setting"
            print(f"{path}: {description}; report 7: {report.hex(' ')}")
        else:
            print(set_white(fd))
    finally:
        os.close(fd)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PermissionError:
        print("Cannot access the LD-135. Its udev access rule must be active for this login.",
              file=sys.stderr)
        sys.exit(2)
    except (OSError, RuntimeError) as error:
        print(f"Keyboard lighting: {error}", file=sys.stderr)
        sys.exit(1)
