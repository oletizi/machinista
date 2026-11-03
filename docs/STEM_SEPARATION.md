# Separate a sample into four stems

Stem Separation is an optional, local sample tool in the WebUI. It creates
**Vocals, Drums, Bass and Other** as separate 24-bit stereo WAV files. It does
not change your original sample or load over a Sound in your current project.
Separation is an estimate: bleed and other audible artifacts can remain.

## First setup

1. Open Sample Library in the WebUI. Upload a WAV or MP3 if needed.
2. Next to a sample, choose **Separate stems**.
3. Choose **Download & install engine**. Keep internet and power connected.
   Setup installs a private Python environment and downloads an 80 MB model pack.
   Allow 1.5 GiB free storage. It changes no system Python packages.
4. Once setup finishes, the tool works offline. Your recording is never uploaded.

Model setup is separate from the normal image and from LV2 plugins. If Python
venv support is missing, the OS needs its `python3-venv` package. The prepared
images include that support. Inference packages need ARM64 Linux wheels.

## Separate a sample

1. Stop PLAY, REC, sample recording and other processing jobs.
2. Choose **Separate 4 stems**. Keep transport stopped until it finishes.
   Starting playback or recording cancels the operation.
3. Use **Open stems folder** when finished. Results are in
   `SD CARD / Library / Stems / <sample name>-<unique ID>`.
4. Preview or load the new WAV files as normal samples, then slice them or
   put each stem on a separate pad. You choose the destination pads yourself.

The first beta implementation accepts up to **60 seconds / 64 MiB** per source.
Longer files are rejected, never silently shortened. Output is 44.1 kHz stereo.
If necessary, the same gain reduction is applied to all four stems to prevent
clipping while preserving their relative levels. It is recorded in Separation.json.

The operation needs **at least 1.5 GiB free RAM** in addition to the running
system. A Pi with 4 GB or more is the intended starting point; a 2 GB setup
may not have enough free memory. Processing runs at low priority with one CPU
inference thread in its own process. It can take several minutes on a Pi;
this is preparation of a sample, not a live effect.

Close only hides the window; **Cancel operation** stops the job. Incomplete
results are not published. Existing samples and projects are never replaced.
Model/runtime files are stored separately in `presets/.stem-engine/`.

## Engine and attribution

Machinista supplies its own bounded job handling, overlap/add processing, WAV
output and WebUI. Numerical inference uses separately installed
[ONNX Runtime](https://github.com/microsoft/onnxruntime) (MIT) and
[NumPy](https://numpy.org/doc/stable/license.html) (BSD).

The model pack is [Spleeter 4-stem ONNX](https://huggingface.co/Best-Practice/spleeter-4stems-onnx),
converted from [Deezer Spleeter](https://github.com/deezer/spleeter) through
[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx). The converted graphs are
published under Apache-2.0; Spleeter's code is MIT. The upstream model card
explains its pretrained-weight licensing notes and credits. Model conversion:
[Matthew Bae / Best Practice](https://github.com/matthewbae/spleeter-onnx-models).

Pinned model revision: `486643021f18a4d057d282fff1d11b89a30e9887`.
`app/stem_models.py` records the size and SHA-256 of each of the four graphs.
Setup verifies every file before enabling the engine. The independent graphs
run one at a time, in 512-frame spectrogram blocks. A RAM watchdog stops a
worker exceeding 1 GiB RSS or leaving less than 512 MiB available on Linux.

No model, external inference library or third-party LV2 bundle is in the source
repository. This tool does not bypass licenses for any music you process.
