# Sample Sets / Expansions

A sample set is a portable Machinista Group preset with up to 16 pad Sounds,
collected sample files and saved plug-in state. Plug-in binaries are not included.
The receiving machine needs the referenced plug-ins installed.

## Save your own set

On the controller open Project > Manage > SAVE GROUP, enter a name and save.
Stop playback and recording before saving. The existing Group-preset mechanism
collects the samples and plug-in state. Patterns are excluded. In the WebUI open
Sounds > Sample Sets / Expansions, refresh and choose Download ZIP.

## Import and load

In the same WebUI section choose Import sample set ZIP. Supported inputs are:

- A ZIP exported by this sample-set interface (one Machinista Group preset).
- A ZIP of readable PCM WAV samples, including supported 32-bit float WAV files
  which are converted with the normal sample validator. Files are sorted by their
  archive path and assigned to pads 1–16. Larger packs become numbered Groups of
  16 pads, up to 256 samples per ZIP. Folder names are retained in the sort order;
  original Maschine pad assignments, patterns and effects are not interpreted.

Then on any controller open BROWSE, go up to the source list, select SAMPLE SETS,
select a set and LOAD. Stop transport first. Loading replaces the selected Group's
pad Sounds and Group processing; its existing Patterns remain. Back up the Group
first if you want to keep its Sounds. Loading uses the existing preset undo flow.

Imported files are stored in presets/Groups. Duplicate set names are rejected;
existing sets are not overwritten. Rename the incoming ZIP before importing a
plain WAV pack with the same name. Limits: 1 GiB compressed/expanded archive,
4096 archive entries, 256 WAV files. Symlinks, path traversal, encrypted archives
and unsupported file types are rejected. Downloads collect data, never plug-in
executables. Uploading does not change the running project or trigger playback.

## Maschine expansion limitations

This is a sample-pack and native Machinista Group importer, not a Maschine preset
converter. Native expansion installers and NKI/NKX/NCW containers are not supported.
Use a ZIP containing the expansion's already readable WAV files, where your
license allows that use. Do not share purchased expansion samples merely because
you have converted or repackaged them. MP3 packs are not yet supported here;
individual MP3 files can still be imported through Sample Library.
