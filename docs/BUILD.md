# Build and test

## Linux prerequisites

Primary deployment: Raspberry Pi OS 64-bit (Debian Trixie), Raspberry Pi 4/5.
Python 3.13 is used on the deployment image. Portable Python tests also run on 3.12.

On Debian/Ubuntu, install the native development libraries:

```sh
sudo apt-get update
sudo apt-get install build-essential cmake ninja-build pkg-config \
  libhidapi-dev libasound2-dev liblilv-dev libusb-1.0-0-dev \
  python3 python3-venv ffmpeg rubberband-cli
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
```

The device image additionally uses distro-provided Pillow, D-Bus, GI and GPIO
bindings plus BlueZ, NetworkManager, Samba and systemd services. The authoritative
runtime package list is in tools/build_beta_image.py. Do not assume pip alone
installs the complete device environment.

## Native engine and decoder tests

```sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure
```

Linux development libraries are required. x86-64 compilation verifies host-side
code; it is not an ARM image or a test of physical controller/audio hardware.
Do not run diagnostic HID tools alongside the main application.

## Python regression tests

```sh
python3 -m unittest discover -v -s tests
```

For a portable run without native integration tests, leave build/audio_engine
absent. Native suites detect the executable and ALSA. Some require optional test
LV2 fixtures (swh-lv2 and optionally mda-lv2), a running LV2 metadata scanner and
its manager. Skips must be reported, not counted as device coverage.

CI deliberately separates full portable Python discovery (no native binary)
from Linux CMake/CTest and the native color-display protocol integration. Full ARM image testing with isolated LV2 services remains
an additional release validation step.

## Run on a development device

```sh
python3 tools/machinista.py
```

Controller permissions and the required runtime services must already be
configured. Use the supplied image for normal use; starting this command does
not install system services. Running creates local config/projects/cache paths.
Back up a working device before changing its installation.

## Run on an x86-64 Linux desktop (MK3)

Verified with a Maschine MK3 on Ubuntu 26.04 x86-64: color displays, pad
LEDs, buttons, encoders and MK3 audio output all work without code changes.

Without sudo, the native libraries can come from Homebrew:

```sh
brew install cmake ninja pkgconf hidapi libusb lilv alsa-lib
tools/run_desktop.sh
```

The script builds once (set `REBUILD=1` to rebuild) and starts the app with a
Python that has Pillow. Homebrew's `python3` often shadows the system one on
PATH without Pillow; set `PYTHON=/usr/bin/python3` if needed. A logged-in desktop
session normally grants device access through uaccess ACLs; otherwise install
`deploy/71-machinista-mk3.rules`. Stop the app before using the MK3 for sound in
other desktop applications.

### Start automatically when the MK3 is plugged in

For a headless host (for example, used over SSH), install a user service that
udev starts when the MK3 appears and systemd stops when it is unplugged:

```sh
tools/run_desktop.sh                       # once, to build; Ctrl-C after it starts
tools/install_desktop_service.sh           # user unit + linger, no sudo
tools/install_desktop_service.sh --rule    # udev rule, asks for sudo
```

Replug the MK3 (or reboot) to start it. `deploy/desktop/71-machinista-mk3-desktop.rules`
grants `plugdev` access without a seat login, adds `/dev/maschine-mk3`, and
requests `machinista.service` from the user manager. Linger keeps that manager
running without a login. Manage it with `systemctl --user status|stop|restart
machinista` and `journalctl --user -u machinista -f`. Remove it with
`tools/install_desktop_service.sh --uninstall`. On unplug, the MK3 input
reader logs an `Input/output error` traceback before the service stops; the
service still exits successfully. Verified on Ubuntu 26.04 x86-64: plug-in start, unplug stop,
and replug restart. Start at boot without a login is expected via linger but
was not separately tested.

The installer also enables `machinista-web.service`, which runs the web UI
independently of the MK3 and listens on `127.0.0.1:8080` only (no login, so it
must not be exposed). From another computer, open an SSH tunnel and browse to
http://localhost:8080:

```sh
ssh -L 8080:localhost:8080 <host>
```

It keeps the Pi unit's low CPU/IO priority and 192 MB memory limit.

### Data directory

By default all user data lives in the checkout, as on the Pi image. Set
`MACHINISTA_DATA` to keep it elsewhere; `tools/run_desktop.sh` and the
installed services default to `~/Music/maschinista`. The data root holds
`samples/` (shown as SD CARD), `projects/`, `config/`, `cache/`, `exports/`,
`backups/` and `presets/Sounds`, `presets/Groups`. Code, native builds, web
assets and captures always come from the checkout.

`presets/Oscillators` and `presets/plugin-banks` are layered: factory items are
read from the checkout and stay read-only, while uploaded waveforms and
imported banks go to the data root. To move existing data, stop both services
and move those folders into the data root before starting them again.

## Release image tooling

Read docs/GITHUB_PUBLISH.md and docs/INSTALL.md. tools/prepare_beta_release.py
assembles an explicit public payload from tested ARM binaries and original
Factory assets. tools/build_beta_image.py configures a disposable offline Pi OS
root; it is not an installer for the running system. Full disk partitioning,
firmware provenance, sanitization and cold-boot checks are separate steps.

Manual generation currently also requires ReportLab, PDF tooling, browser
capture dependencies and the configured document fonts. They are not runtime
requirements. Generated PDFs are distributed as release assets.
