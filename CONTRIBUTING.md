# Contributing

Bug reports, documentation fixes, and evidence from other keyboard revisions are
welcome. Please keep the default behavior simple: select white once at graphical
login, preserve the existing brightness/speed setting, and leave subsequent
manual changes alone.

## Report a problem

Open an [issue](https://github.com/bell-kevin/sablute-ld135-linux-backlight/issues)
with the keyboard's model label, USB VID/PID, Linux distribution, architecture,
desktop environment, and the command output. State whether manual Fn + 2 works
and whether the problem concerns discovery, permissions, setting white, or login
startup. Remove personal paths and unrelated device information from logs.

For a device this project does not recognize, begin with identification and
read-only evidence. A matching generic USB name is not enough to add support.
Do not remove the descriptor check simply to make another keyboard match.

## Develop and test

Python code uses the standard library. Run the automated tests without a keyboard
or elevated privileges:

```sh
python3 -m unittest discover -v
python3 tools/check_site.py
```

CI runs the hardware-free tests and syntax checks on Python 3.10 and 3.12,
validates the desktop entry and udev rule, and checks website metadata, local
links, and assets. The website check uses only the standard library and makes
no network requests.

Changes to the write path should cover failure behavior as well as successful
selection: identity mismatches must prevent writes, short or failed writes must
not be retried, and verification must preserve unrelated lighting fields.
Use mocked device access for automated tests. Hardware checks must be explicit,
separate from the test suite, and limited to supported commands.

For protocol changes, document the exact device and descriptor, command source,
packet bytes, before/after reports, and visual observation in [PROTOCOL.md](PROTOCOL.md).
Label inferences and unknown fields. Device-specific EEPROM or firmware writes
are outside the scope of this login helper.

Keep installer changes portable between user accounts. System files belong under
`/usr/local` and `/etc/udev/rules.d`; login startup belongs to the invoking user's
XDG configuration directory. Do not hard-code personal directories.

## Pull requests

Explain the problem, resulting behavior, and validation. Keep changes focused and
update the documentation when behavior or supported hardware changes. Do not
include downloaded vendor executables, captures containing private information,
credentials, or generated caches.

Contributions are provided under the project's GNU Affero General Public License,
version 3. See [LICENSE](LICENSE).
