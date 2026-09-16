<a name="readme-top"></a>

# SABLUTE LD-135 Linux Backlight

Set a SABLUTE LD-135 keyboard to steady white when you sign in to Linux.
The helper preserves brightness and speed, runs once, and exits. You can still
use **Fn + 2** to change colors afterward.

[Project website](https://bell-kevin.github.io/sablute-ld135-linux-backlight/) ·
[Protocol notes](PROTOCOL.md) · [Contributing](CONTRIBUTING.md)

## What has been tested

The command and login setup were verified on one SABLUTE LD-135 revision with
Ubuntu 24.04 on x86_64. Changing another solid color to white, preserving the
other lighting fields, skipping an already-white keyboard, and using Fn + 2
afterward all worked. White at graphical login was confirmed after a reboot.

**White is applied after you sign in.** The keyboard may show its factory color
during boot or at the login screen. Complete power disconnection, suspend/resume,
and unplug/replug behavior have not been verified. The helper does not run again
on resume or reconnect; you can run `ld135-white` manually when needed.

| Device requirement | Verified value |
| --- | --- |
| Label | SABLUTE LD-135 |
| USB vendor/product ID | `30fa:2052` |
| USB name | `INSTANT USB Keyboard` |
| HID interface | USB interface `01`, vendor feature report `07` |
| Feature report size | 8 bytes, including the report ID |

The helper also requires this exact HID report descriptor SHA-256:

```text
fc4de9961c5a701ba6f2aa806c0d85a6478104e1864fef2d0020cf5c7c093c48
```

A matching product name or USB ID alone is insufficient. Other revisions and
related Instant keyboards are not supported automatically. Multiple matching
keyboards cause the helper to stop without changing either one.

## Install

Requirements: Linux with hidraw, Python 3, udev, and a graphical desktop that
supports XDG autostart and active-session device access. The verified environment
is Ubuntu 24.04 x86_64 with Python 3.12. The Python programs use only the standard
library; no pip packages or Windows software are needed.

Download the source or clone the repository, then enter its directory:

```sh
git clone https://github.com/bell-kevin/sablute-ld135-linux-backlight.git
cd sablute-ld135-linux-backlight
```

Identify the supported interface without opening it:

```sh
python3 keyboard_white.py --dry-run
```

Install the system helper and its device-access rule:

```sh
sudo python3 install_keyboard_white.py --system install
```

As your regular desktop user, test the command and enable login startup:

```sh
ld135-white --status
ld135-white
python3 install_keyboard_white.py --autostart enable
```

Run the autostart command without `sudo`: it belongs to the user who wants white
at login. Each desktop user can enable it separately. The installer grants the
active local desktop user access to the matching vendor interface; it does not
grant everyone access to all keyboards.

The login entry runs `ld135-white --wait 30`, allowing up to 30 seconds for the
keyboard and its access permissions to become available. Administrator access is
needed for system installation, not for normal lighting changes.

## Use

```sh
ld135-white              # Set steady white once
ld135-white --status     # Read the current lighting status
ld135-white --dry-run    # Identify the interface without opening it
ld135-white --wait 30    # Wait for the device, then set white once
```

To check the change yourself, use Fn + 2 to select another color, run
`ld135-white`, and check that it becomes white. Fn + 2 continues working after
the program exits. There is no background service enforcing a color.

The helper reads the current brightness/speed byte and preserves it. It sends
at most one runtime lighting command per invocation, verifies the result, and
sends no EEPROM or firmware programming commands. If it is already steady white,
no lighting write is sent. The program does not read keystroke events or use the
network. See [PROTOCOL.md](PROTOCOL.md) for the verified packet and its limits.

## Disable, upgrade, or uninstall

Disable automatic white at login while keeping the manual command:

```sh
python3 install_keyboard_white.py --autostart disable
```

To upgrade, obtain the new source, run the system installer again, and refresh
your login entry:

```sh
sudo python3 install_keyboard_white.py --system install
python3 install_keyboard_white.py --autostart enable
```

To remove the login entry and system files:

```sh
python3 install_keyboard_white.py --autostart disable
sudo python3 install_keyboard_white.py --system uninstall
```

For shared computers, each user who enabled autostart should disable their own
entry. Uninstalling does not change the keyboard's currently selected color.
The installer supports `--dry-run` to preview an install, removal, or autostart
change without applying it.

| Installed path | Purpose |
| --- | --- |
| `/usr/local/lib/ld135-white/keyboard_white.py` | Lighting helper |
| `/usr/local/bin/ld135-white` | Command launcher |
| `/etc/udev/rules.d/70-ld135-white.rules` | Access to the matching vendor interface |
| `~/.config/autostart/ld135-white.desktop` | Per-user graphical-login entry; uses an absolute `XDG_CONFIG_HOME` when set |

## Troubleshooting

**No matching interface:** check `lsusb -d 30fa:2052` and run
`python3 keyboard_white.py --dry-run` from the source directory. An ID match with
a descriptor mismatch is deliberately rejected; please report the revision
instead of removing the identity checks.

**Access denied:** run the system installer from the active graphical session,
then try `ld135-white --wait 30`. A remote or text-only login may not receive the
active-desktop access granted by `uaccess`.

**Manual command works, login startup does not:** run the regular-user
`--autostart enable` command again and check that your desktop supports XDG
autostart. This project does not install a boot service.

**Fn is held or the state keeps changing:** release Fn and try again. The helper
waits briefly for a stable status before writing. A failed write or verification
is reported without repeating the command.

For a read-only report from the source checkout, use:

```sh
python3 keyboard_white.py --dry-run
python3 keyboard_white.py --status
```

[Open an issue](https://github.com/bell-kevin/sablute-ld135-linux-backlight/issues)
with your device label, USB ID, distribution, architecture, desktop, command
output, and whether manual Fn controls still work. Remove personal paths or
other unrelated information from logs.

## Development and related work

Run the automated tests without a keyboard or administrator privileges:

```sh
python3 -m unittest discover -v
```

The core controller tests cover identity checks, single-write behavior,
brightness preservation, verification failures, and waiting for Fn to be
released. Hardware verification and platform coverage are described above;
automated tests alone do not establish support for another keyboard.

Related Instant-controller research includes
[Adventurer K812 / IST83025B](https://github.com/CharlesMod/adventurer-k812-ist83025b),
[Instant K201 Linux configuration](https://github.com/stonedDiscord/k201), and
[OpenRGB's Thor 210 investigation](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/3835).
[PROTOCOL.md](PROTOCOL.md) records the manufacturer's utility sources and the
local observations behind this implementation.

## License

GNU Affero General Public License, version 3. See [LICENSE](LICENSE).

<p align="left"><a href="#readme-top">back to top</a></p>
