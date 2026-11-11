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
`(page, control_level, page_index, layout)` where `page_index` is the first
value of `page_state()` and `layout` is the selected plug-in's URI on `PLUGIN`
and `None` elsewhere. Memory is deliberately per *layout*, not per target:
the same page for a different sound, group or instance of the same plug-in has
the same parameter in the same cell, so keeping the position there is the useful
behaviour (edit cutoff on pad 1, select pad 2, the 4D encoder is still on
cutoff). Different plug-ins have different layouts, so they get separate
positions. No invalidation is needed: positions are resolved against the live
`fields()` on every use. A view not yet visited starts on its first non-empty cell. If the
remembered cell is empty (the page's contents changed), the cursor resolves to
the nearest non-empty cell, preferring the lower index on a tie. A page with no
non-empty cells has no cursor, and the 4D encoder keeps its current behaviour
there.

**4D turn** (no SHIFT): applies `delta` steps to the cursor's parameter by
calling the same entry point a knob uses: `rotate(cursor + 1, delta)`. That
entry point takes *steps*: for knobs, `Mk2Session.rotate_raw` has already divided
raw counts by the field's quantum, while the 4D counter (0–15) reports one count
per detent and `rotate_raw(0, …)` forwards it unscaled. A 4D `delta` of ±N
(the session batches consecutive same-direction reports) is therefore N
parameter steps — one choice for discrete values, one quantum for continuous
ones — with the same clamping, undo, automation recording and display feedback
as N knob steps.

Only the *physical* 4D turn is intercepted. It enters through a new
`Mk3Surface.master_turn(delta)`, which `Mk3Session.rotate_raw` calls for index 0
on the MK3 instead of `surface.rotate(0, …)`. `surface.rotate(0, …)` itself is
unchanged, so synthetic callers keep their meaning — notably MASTER UP/DOWN on
the non-chain parameter pages, which call `rotate(0, ±1)` and keep moving the
transport.

**SHIFT + 4D turn:** keeps today's unshifted 4D behaviour — moves the
transport on the `CONTROL_PAGES`; on `AUDIO LOOP` it is passed through
unchanged.

**4D left / right** (`MASTER LEFT` / `MASTER RIGHT`, no SHIFT): move the
cursor to the previous / next non-empty cell. Past either end the traversal is
bounded:

1. Call `change_page(±1)` — the exact PAGE LEFT/RIGHT path — at most
   `page_total` times (the second value of `page_state()`, re-read after each
   call; at least 1, at most 16).
2. After each call, if the view key did not change, the first/last page was
   reached: stop.
3. If the new view has a non-empty cell, place the cursor on its first (moving
   right) or last (moving left) non-empty cell and stop.
4. Otherwise continue with the next call.

There is no rollback. Each step is an ordinary page change with exactly the
effects of pressing PAGE LEFT/RIGHT once (including `parameter_kind`, field
selection and `remember_control_view()`), so the resulting state is always one
the page buttons can produce. If the traversal ends on an empty view (no
populated page remains in that direction), the user stays there with no cursor,
as after pressing PAGE RIGHT onto that page; the opposite direction moves back.
Attempting to restore the earlier view would require reversing every side
effect of `change_page()`, which is fragile and not needed for a correct result.

`change_page()` may move between page names (via `channel_page_path()`); the
view key includes the page name, so that counts as a change. Auto-repeat follows
the existing held-button guard: one move per press.

**SHIFT + 4D left / right:** keeps today's behaviour on every cursor page —
chain-slot switching on `SAMPLER` / `PLUGIN` / `AUDIO LOOP` (the existing MK3
handler ignores SHIFT) and `NAV LEFT/RIGHT` elsewhere. This mirrors SHIFT + turn:
SHIFT is the escape hatch to the pre-cursor 4D behaviour.

**4D up / down** on `SAMPLER`, `PLUGIN` and `AUDIO LOOP`: switch to the previous
/ next chain slot, as today. On those pages left/right no longer switch slots;
they move the cursor instead.

**Knob turn:** turning knob *n* on a parameter page sets the cursor to cell
*n − 1* before the value changes, so the 4D encoder is then on the parameter last
adjusted. Turning a knob whose cell is empty leaves the cursor unchanged.

**Unchanged:** held VOLUME / SWING / TEMPO master modes take precedence over the
cursor (`master_turn` checks `self.master_mode` and defers to
`rotate(0, …)`); MASTER UP/DOWN on non-chain pages (transport); MASTER PUSH;
PAGE LEFT / RIGHT; knob touch highlights.

**Display.** The cursor and touch use distinct marks so they never read as the
same state. Touch keeps its existing 2-pixel accent line *above* the cell
(y = 219). The cursor is a 3-pixel accent bar *below* the cell (y = 268–270,
inside the 272-pixel screen and clear of the cell, which ends at y = 266). When
both apply to one cell, both marks show.

## Components

- `app/mk3_surface.py` (`Mk3Surface`)
  - `cursors`: dict of view key → cell index.
  - `cursor_active()`: true when source is `mk3`, page is in `CONTROL_PAGES`
    or is `AUDIO LOOP`, and no master mode is held.
  - `cursor_cell()`: resolved cursor cell for the current view, or `None`.
  - `master_turn(delta)`: physical 4D turn. With an active cursor and no SHIFT
    → `rotate(cursor + 1, delta)`; otherwise → `rotate(0, delta)`.
  - `rotate(index, delta)`: index 1–8 on an active cursor page records the
    cursor first (only when that cell is non-empty); index 0 unchanged.
  - `button(name, pressed)`: `MASTER LEFT` / `MASTER RIGHT` on an active cursor
    page without SHIFT move the cursor (bounded page traversal at the ends);
    the existing chain-slot handler keeps up/down, and left/right only with
    SHIFT, on `SAMPLER` / `PLUGIN` / `AUDIO LOOP`.
- `app/mk3_session.py`: a `rotate_raw` override intercepts only index 0 and
  calls `surface.master_turn(delta)`; indices 1–8 delegate to
  `super().rotate_raw(index, delta)` so the smooth-knob accumulator and per-field
  quantum stay intact; the display snapshot gets `state['cursor']` =
  `cursor_cell()` next to `state['touches']`.
- `app/mk3_display.py`: draw the cursor bar below the cell where
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
2. A 4D turn through `Mk3Session.rotate_raw(0, ±1)` and `(0, ±N)` changes the cursor's parameter
   exactly as `rotate(cursor+1, ±1/±N)` does on a twin application, for a
   discrete and a continuous field, including clamping at the limits.
3. Left/right move the cursor; past the end the page changes and the cursor
   lands on the first/last cell; at the first/last page it stops; the
   multi-page CHANNEL path is traversed in both directions; a destination
   view with no populated cells is skipped; if nothing populated follows, the
   resulting state (page, `parameter_kind`, `parameter_choice`, field
   selection, remembered control view) equals the state reached by pressing
   PAGE RIGHT/LEFT the same number of times on a twin application.
4. A knob turn moves the cursor to that knob; turning an empty cell's knob
   does not.
5. Cursor memory: two different plug-ins keep separate positions; two sounds
   on the same page share one.
6. SHIFT + turn moves the transport and leaves project parameters unchanged.
7. SHIFT + left/right keeps the old behaviour at an interior cell and at both
   page boundaries (slot switching on Plug-in, NAV elsewhere).
8. Held VOLUME, SWING and TEMPO still route the 4D turn to their master value.
9. MASTER UP/DOWN on a non-chain parameter page still moves the transport;
   on Sampler / Plug-in still switch chain slots.
10. On Audio Loop the cursor reaches a setting other than the first.
11. A `PlusSurface` keeps the old behaviour.
12. The MK3 snapshot carries `cursor`; rendering shows the touch line only,
    the cursor bar only, and both, in the expected rows.

`tests/test_mk3_chain_cards.py` cases that use left/right to switch slots are
changed to up/down or SHIFT + left/right. Full suite run compared against the
known baseline (7 LV2 fixture failures on this host). Final acceptance:
hands-on test on the MK3.
