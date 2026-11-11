# MK3 4D-encoder parameter cursor — design

Date: 2026-11-11 · Branch: `mk3-4d-parameter-cursor` (from `mk3-linux-desktop`)

## Goal

Let the MK3's 4D encoder edit the parameters shown on the eight touch-sensitive
knobs. The knobs have no detents, so discrete values (filter type, waveform,
on/off, note values) are hard to set precisely with them. The 4D encoder clicks,
so one click = one step makes those values easy, one-handed, with no knob touch.

## Behaviour

**Scope.** Only on the MK3 (`source == 'mk3'`), and only on the parameter pages
`PAD`, `CHANNEL`, `SAMPLER`, `PLUGIN`, `INPUT`, `GROOVE`, `MACRO`
(`app.navigation.CONTROL_PAGES`, where turning the 4D encoder currently moves
the transport) plus `AUDIO LOOP` (its four settings sit on knobs 1–4; on the MK3
today the 4D turn can only change the first, because 4D left/right is taken by
chain-slot switching). Every other page — Bounce to Pad, Chop, Events,
browsers, settings, arranger, mixer — is unchanged. The Maschine+ (`PlusSurface`, which subclasses
`Mk3Surface`) is unchanged.

**Cursor.** On a parameter page one of the eight parameter cells is the cursor.
Each page view remembers its own cursor, keyed by
`(page, control_level, page_index)` where `page_index` is the first value of
`page_state()`. A view not yet visited starts on its first non-empty cell. If the
remembered cell is empty (the page's contents changed), the cursor resolves to
the nearest non-empty cell, preferring the lower index on a tie. A page with no
non-empty cells has no cursor, and the 4D encoder keeps its current behaviour
there.

**4D turn** (no SHIFT): applies `delta` steps to the cursor's parameter by
calling the same entry point a knob uses: `rotate(cursor + 1, delta)`. One 4D
click is one parameter step — one choice for discrete values, one quantum for
continuous ones — with the same clamping, undo, automation recording and
display feedback as a knob step.

**SHIFT + 4D turn:** keeps today's unshifted 4D behaviour — moves the
transport on the `CONTROL_PAGES`; on `AUDIO LOOP` it is passed through
unchanged.

**4D left / right** (`MASTER LEFT` / `MASTER RIGHT`): move the cursor to the
previous / next non-empty cell. Moving past the last cell calls the existing
`change_page(+1)` (the PAGE RIGHT path) and places the cursor on the new view's
first non-empty cell; moving before the first calls `change_page(-1)` and places
it on the last. If the page does not change (already the first / last page), the
cursor stays where it is. Auto-repeat follows the existing held-button guard:
one move per press.

**4D up / down** on `SAMPLER`, `PLUGIN` and `AUDIO LOOP`: switch to the previous
/ next chain slot, as today. On those pages left/right no longer switch slots;
they move the cursor instead.

**Knob turn:** turning knob *n* on a parameter page sets the cursor to cell
*n − 1* before the value changes, so the 4D encoder is then on the parameter last
adjusted.

**Unchanged:** held VOLUME / SWING / TEMPO master modes take precedence over the
cursor; MASTER PUSH; PAGE LEFT / RIGHT; knob touch highlights.

**Display.** The cursor's cell gets the same 2-pixel accent underline a touched
knob shows (`mk3_display.py` parameter-cell loop). Touch highlights still
appear for touched knobs.

## Components

- `app/mk3_surface.py` (`Mk3Surface`)
  - `cursors`: dict of view key → cell index.
  - `cursor_active()`: true when source is `mk3`, page is in `CONTROL_PAGES`
    or is `AUDIO LOOP`, and no master mode is held.
  - `cursor_cell()`: resolved cursor cell for the current view, or `None`.
  - `rotate(index, delta)`: on an active cursor page, index 0 without SHIFT
    → `rotate(cursor + 1, delta)`; index 1–8 records the cursor first.
  - `button(name, pressed)`: `MASTER LEFT` / `MASTER RIGHT` on an active cursor
    page move the cursor (with page change at the ends); the existing
    chain-slot handler keeps only up/down on `SAMPLER` / `PLUGIN` /
    `AUDIO LOOP`.
- `app/mk3_session.py`: the display snapshot gets `state['cursor']` =
  `cursor_cell()` next to `state['touches']`.
- `app/mk3_display.py`: draw the underline for the cell where
  `side*4 + i == s.get('cursor')`.
- `docs/MK3_SUPPORT.md`: document the cursor, SHIFT + turn transport and the
  up/down-only slot switching on Sampler / Plug-in / Audio Loop.

## Error handling

The cursor is UI state only: it is never saved to the project or settings, and
it never addresses a cell beyond the current `fields()`. Resolution happens on
every use, so stale entries (deleted plug-ins, changed pages) degrade to the
nearest valid cell or to the old 4D behaviour, never to an exception.

## Testing

New `tests/test_mk3_parameter_cursor.py`, using the existing fixture pattern
(`Application` + `ControllerInputs` + `Mk3Surface` on a temporary root),
written before the implementation:

1. Cursor defaults to the first non-empty cell; empty cells are skipped.
2. A 4D click changes the cursor's parameter exactly as a one-step knob turn
   does on a twin application.
3. Left/right move the cursor; past the end the page changes and the cursor
   lands on the first/last cell; at the first/last page it stops.
4. A knob turn moves the cursor to that knob.
5. SHIFT + 4D turn moves the transport and leaves the project parameters
   unchanged.
6. Held TEMPO still changes tempo with the 4D encoder.
7. Up/down still switch chain slots on Sampler / Plug-in; on Audio Loop the
   4D turn reaches a setting other than the first via the cursor.
8. A `PlusSurface` keeps the old behaviour (4D turn moves the transport).
9. The MK3 snapshot carries `cursor`.

`tests/test_mk3_chain_cards.py` cases that use left/right to switch slots are
changed to up/down. Full suite run compared against the known baseline (7 LV2
fixture failures on this host). Final acceptance: hands-on test on the MK3.
