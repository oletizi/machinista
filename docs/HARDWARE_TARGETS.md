# Hardware targets

Machinista uses one source tree with explicit hardware capabilities. A smaller
board does not require a fork or changes to users' project formats.

| Target | CPU/build | Features | Sampler | Initial buffer |
| --- | --- | --- | --- | --- |
| `standard` | ARM64, Pi 4/5 image | Existing synths, LV2, optional stems | 64 voices / 512 MiB sample budget | Automatic |
| `pi3b-sampler` | ARM64 ARMv8-A / Cortex-A53 | Sampler, internal effects, sequencing/MIDI/WebUI; synths, external LV2 and stems disabled | 16 voices / 192 MiB sample budget | 512 samples |

The Pi 3B target is experimental until physical boot, controller, HAT/USB audio
and sustained-load tests pass. MK3 display frame scheduling is unchanged.
Memory budgets refer to decoded sample data; OS, UI, native engine and effect
buffers need additional RAM. Samples are currently loaded into RAM, not streamed
from disk. A small profile does not make arbitrarily large projects fit.

`/etc/machinista/hardware-profile` selects a known profile at boot. Python reads
`app/hardware_profiles.py`; the native engine independently enforces the same
policy in `src/audio/hardware_profile.hpp`. UI hiding alone is not a security or
capability boundary: native instantiation also rejects unavailable instruments
and external LV2 plugins. Native effects remain usable without a running LV2
installer/scanner. The engine still links Lilv for the shared host implementation;
removing third-party plugin support does not yet remove that small runtime library.

Packaging: `prepare_beta_release.py --hardware-profile pi3b-sampler` excludes
factory synth banks and generated oscillator assets. `build_beta_image.py ROOT
PAYLOAD pi3b-sampler` writes the marker, 512-sample initial setting and disables
the LV2 manager/scanner services. Compile for `-march=armv8-a -mtune=cortex-a53`,
never `-march=native`, for the Pi 3B image. Boot firmware/kernel/device trees must
also support the board; changing app capabilities is not enough.

## Parallel updates and future architectures

The existing standard ARM64 feeds stay at `updates/update.json`. Additional
hardware targets use `updates/targets/<target>/update.json` and `.sig` in the
selected beta/release branch. Signatures, OS codename, architecture and hardware
target must match before installation. Archives also validate ELF machine type.
The marker and updater configuration are outside the user-owned app payload.

`build_update.py --hardware-profile TARGET --architecture arm64|amd64` produces
separate artifacts from the same code. Adding `amd64` validation prepares the
updater; it is not a completed x64 port or a bootable PC image. New SBCs still
need boot/kernel, audio/GPIO and controller qualification. Add a deliberate
profile and platform build recipe, rather than guessing support from RAM size.
