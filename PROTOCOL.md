# LD-135 runtime lighting protocol

This document records the command tested on a SABLUTE LD-135 with USB ID
`30fa:2052`. It distinguishes direct observations from inferences made using
related keyboard software. It is not a general protocol specification for every
Instant controller.

## Verified device and transport

The tested keyboard identifies as `INSTANT USB Keyboard`. Its USB interface 1
exposes vendor feature report 7 with seven data bytes plus the report ID. The
accepted HID report descriptor SHA-256 is:

```text
fc4de9961c5a701ba6f2aa806c0d85a6478104e1864fef2d0020cf5c7c093c48
```

The helper uses Linux hidraw `HIDIOCGFEATURE(8)` and `HIDIOCSFEATURE(8)` on that
interface. These are HID control transfers, with the report ID in the first
buffer byte. The [Linux hidraw documentation](https://docs.kernel.org/hid/hidraw.html)
describes the interface. The implementation's ioctl constants were verified on
Linux x86_64.

Before any lighting operation, the helper matches the USB identity and descriptor
in sysfs, opens the matching device, and verifies both again on the open handle.
It requires exactly one match. Its diagnostic path reads feature reports, not
keyboard input events.

## Status and white selection

The following eight-byte status was observed with steady white selected:

```text
07 00 c1 40 41 41 02 72
```

Offsets in this document start at zero and include the report ID.

| GET byte | Observed meaning or handling |
| --- | --- |
| 0 | Report ID `07` |
| 1 | `00` in normal status; other values are rejected by this helper |
| 2 | Bit `0x40` was set with Fn released and clear while Fn was held |
| 3 | Meaning not established; the setter does not construct it from status |
| 4 | Packed lighting controls, including brightness/speed; preserved as a complete byte |
| 5–6 | Other status fields; their meaning is not established and they are checked for preservation |
| 7 | Color/mode byte; `72` was visually verified as steady white |

Physical Fn + 2 changes the high nibble of byte 7 while the low nibble remains
`2` in steady mode. Values including `12`, `22`, `32`, `62`, and `72` were
observed. This project relies on the verified white value `72`; it does not
publish a complete color-name mapping.

Related Thor 210 captures and the manufacturer's software support interpreting
the low nibble as effect mode, the upper nibble as color selection, and byte 4
bits 0–2 and 3–5 as speed and inverse brightness. Those subfield interpretations
are not needed by the LD-135 setter: it preserves all of byte 4, including its
other bits.

## The implemented command

The runtime command is exactly eight bytes:

```text
07 13 00 00 BB 72 ff ff
```

`BB` is byte 4 from a fresh, stable GET_FEATURE response. With the observed
baseline above, the packet is:

```text
07 13 00 00 41 72 ff ff
```

| SET byte | Value | Handling |
| --- | --- | --- |
| 0 | `07` | Feature report ID |
| 1 | `13` | Runtime lighting command |
| 2–3 | `00 00` | Retained from the manufacturer's constructor |
| 4 | Current GET byte 4 | Preserve the complete lighting-control byte |
| 5 | `72` | Select the verified steady-white state |
| 6–7 | `ff ff` | Retained exactly; full semantics remain unknown |

Do not interpret the final `ff ff` as a proven mask or a command for a second
lighting zone. The tested behavior preserves GET bytes 5 and 6, but the meaning
of the trailer has not been fully decoded.

## Local evidence

An initial test used the manufacturer's runtime packet shape:

```text
Before GET: 07 00 c1 40 41 41 02 72
SET:        07 13 00 00 01 02 ff ff
After GET:  07 00 c1 40 01 41 02 02
```

Restoring the two known fields produced:

```text
SET:        07 13 00 00 41 72 ff ff
After GET:  07 00 c1 40 41 41 02 72
```

These observations establish SET byte 4 → GET byte 4 and SET byte 5 → GET byte 7
on this device, including the upper bits. Steady white was visually confirmed.
Subsequent tests changed another solid color to white using the installed command
as a regular desktop user. An already-white invocation sent no lighting write.
After a reboot and graphical login, white and continued manual Fn + 2 operation
were confirmed.

Complete power disconnection, suspend/resume, and unplug/replug behavior have
not been verified. The login helper reapplies a runtime setting; it does not
attempt to save a new firmware default.

## How the command was identified

Static analysis of the chip manufacturer's public Windows utilities located the
runtime constructor. The utilities were extracted and inspected, not executed.
The original downloads are identified below so the analysis can be reproduced;
no vendor executable is required to run this project.

| Utility | Official download | Download SHA-256 |
| --- | --- | --- |
| IST83025B public keyboard driver, matrix 01 (`driver_21.exe`) | [Manufacturer download](https://www.instant-sys.com/storage/file/20260313/ad4c46f5baf7f14c314e6645c0c7d416.exe) | `584e401f3541c6c6f05abdee5614b4aee6fee0e4cbb55e017b593e71c2d84949` |
| IST83025B public keyboard driver, matrix 02 (`driver_22.exe`) | [Manufacturer download](https://www.instant-sys.com/storage/file/20260313/83e33915f88fbdcaef5714788e0b6086.exe) | `e1eb1015006ac7974698542bea8bb5db66e625c3aba362f583fbb94562d2ec2b` |

In the extracted matrix-01 `Gaming Keyboard.exe`, virtual address `0x43c0e0`
constructs this packet and calls `HidD_SetFeature` through thunk `0x56e856`:

```text
07 13 00 00 ((arg2 << 3) + arg3) (arg1 & 0x0f) ff ff
```

The sound-reactive loop at `0x43c810` calls it repeatedly with changing lighting
parameters. The matrix-02 utility independently contains the same constructor
at `0x436d50`, calling thunk `0x57ff28`. These addresses identify the inspected
binaries, not a stable interface for later utility versions.

The vendor helper masks its mode argument to four bits. Support for the full
`72` color/mode byte was established by the local readback and visual test above,
not by that constructor alone. The driver's related-device support by itself
also did not establish LD-135 compatibility.

## Operations deliberately outside this implementation

Related Instant devices expose a `07 18 ...` configuration/EEPROM command family.
The [Thor 210 captures](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/3835)
show large configuration transactions when colors are changed; they also include
keyboard mapping data. Those transactions were not replayed on the LD-135.
The production setter sends only the verified `13` runtime command and does not
read or program EEPROM, replace firmware, remap keys, or update palettes.

Related work:

- [CharlesMod/adventurer-k812-ist83025b](https://github.com/CharlesMod/adventurer-k812-ist83025b):
  K812 controller identification, configuration references, and host diagnostics.
- [stonedDiscord/k201](https://github.com/stonedDiscord/k201): Linux configuration
  software for a related `30fa:2350` device, including EEPROM-backed backlight
  mode and brightness settings.
- [OpenRGB issue 3835](https://gitlab.com/CalcProgrammer1/OpenRGB/-/issues/3835):
  Thor 210 `30fa:2350` feature reports and color/mode captures.

These projects document related hardware. Their existence does not establish
compatibility with an untested LD-135 revision.
