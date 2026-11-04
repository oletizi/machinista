# Clip Arranger

Arrange Patterns independently on a song timeline. Each Group has a lane; a clip chooses a Pattern, start, length and source offset. Clips in different Groups can overlap. Clips in the same Group may touch but cannot overlap, so a change never silently overwrites another clip.

## Open and play

- MK1 / MK2 / MK3 / Maschine+: open SONG, then display button 8 **CLIPS**. Once a clip arrangement is selected, the MK3/Plus ARRANGER button and Navigate > SONG return to it.
- Mikro: open VIEW > SONG, hold SHIFT and press F2 **CLIPS**.
- Press PLAY or the PLAY display action to play from the timeline cursor. The arrangement stops at the final clip. STOP pauses; RESTART returns to the beginning. Playback continues when you leave the editor.
- **SCENES** switches back to the original Scene-song mode. It retains both arrangements and stops clip playback before switching. Opening the clip editor alone never converts or deletes a Scene song.

## Build the arrangement

1. Choose GROUP and move START to the desired position. On MK1/MK2, page/master arrows move the timeline cursor. On MK3/Plus, push the 4D encoder left/right for time and up/down for Group.
2. Choose PATTERN and press ADD. A new clip initially has that Pattern's length.
3. Use CLIP (or the large encoder) to select a clip. Turning beyond the last clip selects **NEW** after it; START then moves the empty cursor for the next ADD.
4. Set START, LENGTH, PATTERN and OFFSET. A longer clip repeats its Pattern. OFFSET chooses where inside the source Pattern playback starts. SHIFT gives 1/16-note adjustments for start/length/offset.
5. COPY duplicates after the selected clip, skipping occupied time in that Group. DELETE asks before removing only that clip. Undo/Redo restores arrangement edits.
6. GRID sets move/resize increments. ZOOM changes the visible timeline length. FOLLOW returns the view to playback after manual navigation.

The eight encoder fields are GROUP, CLIP, START, LENGTH, PATTERN, OFFSET, GRID and ZOOM. MK1 requires no encoder push: hold SHIFT and use display button 2 EDIT to edit notes. On Mikro, the arrow buttons choose the field and the encoder changes its value. F1 MENU contains ADD, DUPLICATE, DELETE, MAKE UNIQUE, EDIT NOTES, FROM SONG, FOLLOW, AUTOMATION, SCENES and BACK. F2 plays and F3 leaves the editor.

## Linked Patterns and independent clips

Clips initially refer to the existing Pattern. Editing its notes updates every clip that uses that Pattern. To edit one occurrence independently, hold SHIFT and press display button 3 UNIQUE, or choose MENU > MAKE UNIQUE on Mikro. This copies the Pattern notes and modulation into a free Pattern slot and changes only the selected clip's reference. It does not duplicate samples or plug-ins.

EDIT NOTES (SHIFT + display button 2, or the Mikro menu) opens the existing Events editor for the selected clip's Group and Pattern. Notes recorded while clip playback runs are written into the source Pattern at that clip's offset. A gap does not record into an unrelated Pattern. Outside Keyboard mode, pads continue to address their existing Sounds.

## Bring an existing song across

FROM SONG copies the existing Scene-song sequence into Pattern clips. Original Scenes, Pattern assignments and the Scene-song sequence are retained. If clips already exist, replacing them requires confirmation and can be undone. Master song modulation is copied to timeline positions; Pattern modulation follows each clip's source offset.

## Save and export

Normal project saving, autosave, project transfer and Undo include clips. Old projects remain compatible; there is no conversion until you add/import clips. EXPORT AUDIO or EXPORT MIDI with range SONG uses the selected arrangement mode: CLIPS or SCENES. Pattern and Scene export retain their existing behavior. Audio-loop Sounds use the same finite clip windows as notes; empty timeline gaps remain silent except for existing effect tails/live audio inputs.

Current limits: 512 clips and 1024 bars per timeline, with one clip at a time per Group. Existing native note/hit limits and the one-hour export limit still apply. There are no arbitrary audio-file regions: put a sample on a Sound in AUDIO mode, then arrange the corresponding Pattern clip.
