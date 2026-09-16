# Security

## Scope

The helper communicates with the matching keyboard's vendor HID interface.
It checks the USB VID/PID and the complete report descriptor before changing
lighting, sends at most one runtime lighting packet, and checks the resulting
status. It does not read keystroke events, contact network services, or send
EEPROM or firmware programming commands.

The udev rule grants the active local desktop user access to USB interface 1 of
`30fa:2052`. This permission is access to the HID interface, not an operating-system
restriction to the single white-lighting command. The helper's narrower behavior
is enforced by its own code. The rule does not grant general access to all USB
keyboards.

System installation requires administrator privileges. Normal operation and
per-user login configuration do not. Do not run an installer or source checkout
that you do not trust.

## Reporting

Use the repository's
[private vulnerability reporting form](https://github.com/bell-kevin/sablute-ld135-linux-backlight/security/advisories/new)
when available. If private reporting is unavailable, open an
[issue](https://github.com/bell-kevin/sablute-ld135-linux-backlight/issues)
requesting a private contact route without publishing exploit details or secrets.

Include the affected revision, operating system, reproduction steps, and expected
impact. Do not include passwords, access tokens, private captures, or personal
information. No response-time commitment is currently published.
