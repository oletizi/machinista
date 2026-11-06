# Machinista Pi 3B Sampler — experimental test image

For Raspberry Pi 3 Model B with 1 GB RAM. This is a separate hardware target;
existing Pi 4 / Pi 5 images and update feeds remain available.

- Sampler, sampling/slicing, multisamples, sequencing, MIDI, chords, automation,
  song/clip arranger, bounce, MP3 and the file-management WebUI are retained.
- Built-in Machinista effects, Ducktor and Live FX remain available.
- Synth instruments, external LV2 plugins and stem separation are disabled.
- 16 simultaneous sampler voices, 192 MiB decoded sample budget, initial audio
  buffer of 512 samples. Large projects/instruments may exceed this target.
- MK3/Plus display refresh settings are unchanged. Performance on actual Pi 3
  hardware still needs testing; ARM/VM tests do not measure physical audio latency.
- Blank project/library; no personal samples, plugins, saved Wi-Fi or SSH keys.

## First start

Write the `.img.xz` file with Raspberry Pi Imager or balenaEtcher and verify it.
Use an SD card of at least 8 GB. Do not apply custom user/Wi-Fi settings in Imager.
Connect the controller and audio interface/HAT, then power on. Allow first boot
time to expand the card. Join the fallback `Machinista` hotspot (MAC suffix,
password `machinista`) if no saved network is available. The WebUI is reachable
at http://machinista.local:8080; see the existing connection instructions.

Test drums first, then slices/chords and internal effects. Start at 512 samples;
smaller buffers and heavy effects need separate testing. The initial image is
for hardware qualification, not a guarantee of dropout-free performance.

Updates use the shared GitHub repository but the separate signed
`updates/targets/pi3b-sampler/` feed in each beta/release branch. A standard
Pi 4/5 update cannot be installed accidentally on this image. No x64 image or
other SBC image is claimed by this release.
