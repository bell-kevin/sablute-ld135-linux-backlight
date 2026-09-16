# Changelog

## Unreleased

- Keep the website's full layout with JavaScript disabled, including native
  theme and preview color controls and instructions for copying commands.
- Add Auto, Dark, and Light website themes. Auto follows the operating system;
  explicit preferences are remembered for future visits.

## 0.1.0 — 2026-09-16

- Set the tested SABLUTE LD-135 (`30fa:2052`) to steady white with a single runtime
  HID lighting command while preserving its brightness/speed byte.
- Apply white once at graphical login and allow later manual Fn + 2 changes.
- Verify the USB identity and report descriptor, wait for a stable state, and
  check the result without repeating a failed write.
- Provide status and discovery commands, a scoped udev access rule, and portable
  system installation and per-user autostart management.
- Document the verified protocol, vendor utility provenance, related research,
  and unsupported cases.
- Verify white after a reboot and graphical login, with manual color controls
  still working. Complete power disconnection, suspend/resume, and unplug/replug
  remain unverified.
- Publish under the GNU Affero General Public License, version 3.
