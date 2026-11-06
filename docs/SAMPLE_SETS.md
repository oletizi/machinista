# Sample Sets & Expansions

Open the **Sample Sets** tab in the WebUI. It is separate from Sounds:
Sounds holds playable instruments and synth patches; Sample Sets holds kits and
expansions with banks of 16 pad Sounds.

## Build your own kit

1. Choose **+ New** and enter a set name.
2. Drag audio files from your computer onto a pad. Several files fill successive
   pads, starting at that pad; additional banks are created when necessary.
   Confirm before replacing occupied pads. Pad 1 is at the bottom left,
   matching the controller.
3. Alternatively select a pad and choose **Choose sample** to use samples already
   on the Pi's SD card or USB drive. Click a sample in the picker to assign it.
4. Click a loaded pad to preview its sample through your browser device. This
   does not play or record notes in the running Pi project. Use **Stop preview**
   or the audio player to stop playback. A layered pad previews its first sample;
   this is not a rendering of its complete effect chain or velocity layers.
5. Drag pads to swap their assignments. Rename the selected sample using the
   field below the grid. Use **+ Bank**, **Rename** and **Remove bank** to arrange
   the set. Each bank has its own 4×4 grid.
6. Choose **Save set**. **Save copy** makes a separate set. Saved sets and
   expansions appear in the list at the left; click one to view/edit its banks.
   **Download ZIP** creates a portable backup. **Delete** always asks first.

The editor keeps unsaved changes while switching WebUI tabs. Changing to another
set or importing a pack asks before discarding edits. Saved Group presets from
the controller also appear in this tab and can be edited and downloaded.

## Import a folder or expansion

Drop an installed sample/expansion folder onto the import area, or use
**Import folder**. The folder name becomes the set name. Audio files are sorted
by their relative path and divided into banks; distinct sample subfolders become
separate banks. Dropping a folder on a pad instead fills pads from that position
and uses the folder name for an unnamed new set.

Use **Import ZIP / XPN** for an archive:

| Input | Result |
| --- | --- |
| Machinista sample-set ZIP | Restores its named banks, pads and portable sample state. |
| Existing Machinista Group ZIP | Imports the saved Group as a single-bank set. |
| MPC XPN, ZIP or installed folder | Reads the name from `Expansion.xml` when present. Drum `.xpm` programs keep their numbered pad positions, banks and velocity sample layers. Missing/ambiguous sample references stop the import rather than silently mapping the wrong sample. |
| Maschine installed expansion folder or ZIP | Converts readable audio and groups it by sample folder. Its folder/archive name becomes the expansion name. Binary kit mappings, patterns, effects and synth presets are skipped. |
| Generic audio folder or ZIP | Creates a named set with sequential 16-pad banks. |

WAV, AIFF, FLAC, MP3 and OGG audio is copied/converted into collected PCM WAV
files. The audio converter runs with one low-priority worker process. MPC
keygroup audio remains available as unassigned samples; keygroup instrument
mapping is not reproduced. MPC layer stacking/round-robin, tuning, effects and
patterns are not reproduced. **Import details** reports these limitations.

Supply the already installed content, not an EXE/PKG/ISO installer. Protected
NKI/NKX/NCW content is not decoded. Synth presets and plug-in binaries are not
installed by this importer.

Vendor structure references:
[MPC expansion creation](https://support.akaipro.com/en/support/solutions/articles/69000857886-mpc-2-desktop-and-standalone-create-your-own-expansion-packs),
[Maschine expansion content](https://support.native-instruments.com/support/solutions/articles/69000879600-how-to-load-an-expansion-in-maschine).
The converter reads sample metadata directly; it does not contain vendor code.

## Load on the controller

Open **BROWSE → SAMPLE SETS**, choose a set, then choose its bank and **LOAD**.
A legacy single-bank Group can be loaded directly. Stop PLAY/REC first. Loading
replaces the selected Group's Sounds and Group processing; existing Patterns
remain. Use **SAVE GROUP** first if you want to keep the current Group's Sounds.
The normal preset undo flow remains available.

Uploading or editing a set in the WebUI does not change the running project.
For project portability, collect its referenced assets when saving/exporting it.
When editing a set, older collected samples are retained at their original paths
for projects that still reference them. Deleting a set removes it from the
catalog/controller browser and moves its bundle to hidden recovery storage;
projects referring to that removed set should have their samples collected first.

## Storage and limits

Sets are stored in `presets/Groups`. New sets have stable internal IDs, a
`Set.json` bank index and one portable `Preset.json` Group per bank. Existing
single-Group presets remain compatible. Editing uses revision checks and a
staged replacement to prevent stale browser tabs from overwriting newer edits.

Limits: 128 banks / 2,048 pads per set, 1 GiB per archive/folder and expanded or
saved bundle, 8,192 archive entries. Symbolic links, path traversal, duplicate
archive paths and encrypted archives are rejected. Transfers reserve free disk
space; interrupted imports do not publish partial sets. Unfinished browser
uploads are temporary and expire after 24 hours. Plug-in binaries are never
included in exports. Use converted commercial content according to its license.
