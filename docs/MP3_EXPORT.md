# Export your music as MP3

Open **Project > MANAGE > EXPORT AUDIO** on your controller.

1. Choose PATTERN, SCENE or SONG and the source you want to export.
2. Set FORMAT to **MP3**.
3. DEPTH becomes **BITRATE**. Choose **128, 192, 256 or 320 KBPS**.
   320 is the default and the best-quality option; lower settings make smaller files.
4. Select SD CARD or a connected writable USB drive as DESTINATION.
5. Stop playback and recording, then choose EXPORT.

WAV and AIFF keep their own 16/24-bit PCM and 32-bit float settings. Switching
back from MP3 restores the PCM depth you selected previously. MP3 is lossy;
use WAV/AIFF for files you plan to edit or for precise sample loops. MP3 playback
can have encoder padding depending on the player, even with LOOP OPT enabled.

On SD, files are in `exports/<project>-<range>-<number>/`. On USB, files are in
`Machinista/exports/<project>-<range>-<number>/`. The completion screen shows the
result. Existing exports are not replaced. Each selected Sound/Group can also
be exported separately using the existing export source choices.

The native engine renders first; FFmpeg/LAME then encodes in a separate,
low-priority process. No live audio settings are changed. Encoding can be
canceled, and incomplete exports are not published. The prepared Pi image
already includes FFmpeg and FFprobe for MP3 import. A custom installation needs
both tools and an FFmpeg build with `libmp3lame`.
