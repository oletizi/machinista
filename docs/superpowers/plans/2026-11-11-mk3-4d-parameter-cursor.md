# MK3 4D-Encoder Parameter Cursor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the MK3, the 4D encoder edits one parameter at a time (a cursor over the eight knob cells): turn = one step, left/right = previous/next parameter.

**Architecture:** All state and logic live in `Mk3Surface` (`app/mk3_surface.py`). The physical 4D turn gets its own entry point, `master_turn()`, called from an `Mk3Session.rotate_raw` override; edits are delegated to the existing knob path `rotate(cell + 1, delta)`. The cursor is shown in the display snapshot and drawn as a bar under its cell.

**Tech Stack:** Python 3 (`unittest`), Pillow renderer (`app/mk3_display.py`).

**Spec:** `docs/superpowers/specs/2026-11-11-mk3-4d-parameter-cursor-design.md`

## Global Constraints

- MK3 only: every new behaviour is gated on `self.source == 'mk3'`; `PlusSurface` (source `'plus'`) must behave exactly as before.
- Cursor pages: `app.navigation.CONTROL_PAGES` (`PAD, SAMPLER, PLUGIN, CHANNEL, INPUT, GROOVE, MACRO`) plus `'AUDIO LOOP'`.
- View key: `(a.page, a.control_level, self.page_state()[0], uri)`; `uri` is `a.plugin_selected()['uri']` on `PLUGIN`, else `None`.
- No populated cell in the current view → no cursor → 4D turn and left/right keep their current behaviour.
- Cursor is never saved to the project or settings.
- Display: touch line stays at y = 219 (2 px, above the cell); cursor bar at y = 268–270 (3 px, below the cell); both use `ACCENT`.
- Run tests with `/usr/bin/python3` (Homebrew python3 lacks Pillow). Baseline full suite: 7 LV2-fixture failures (6 failures + 1 error); nothing else may fail.

## Review Focus

1. Fast 4D spin → the session batches reports into `delta` = ±N; the parameter must move N steps and clamp, never wrap. (Task 3 test `test_batched_turn_moves_n_steps_and_clamps`.)
2. Cursor on a cell that becomes empty after a slot/sound change (e.g. Sampler page with fewer controls) → snaps to nearest populated cell, no exception. (Task 1 test `test_cursor_snaps_to_nearest_populated_cell`.)
3. Plug-in page with no controls (LV2 metadata missing) → no cursor; left/right still switch slots, turn still moves transport. (Task 2 test `test_empty_plugin_view_keeps_slot_switching`.)
4. Holding the 4D left/right (button auto-repeat sends repeated presses without release) → one move per physical press. (Task 2 test `test_held_right_moves_once`.)
5. Turning the 4D while a master mode (VOLUME/SWING/TEMPO) is latched → master value changes, cursor parameter untouched. (Task 1 test `test_master_modes_take_precedence`.)

---

### Task 1: Cursor state, knob tracking and `master_turn` in `Mk3Surface`

**Files:**
- Modify: `app/mk3_surface.py` (`Mk3Surface.__init__`, `rotate`; new methods)
- Test: `tests/test_mk3_parameter_cursor.py` (create)

**Interfaces:**
- Produces:
  - `Mk3Surface.cursors: dict` (view key → cell index 0–7)
  - `Mk3Surface.cursor_active() -> bool` — source `'mk3'`, page in cursor pages, `not self.master_mode`.
  - `Mk3Surface.cursor_key() -> tuple` — the view key above.
  - `Mk3Surface.cursor_cell() -> int | None` — resolved cell for the current view, `None` if inactive or no populated cell.
  - `Mk3Surface.populated() -> list[int]` — indices of non-`None` entries of `self.fields()`.
  - `Mk3Surface.master_turn(delta: int) -> None` — physical 4D turn.

Test fixture (top of the new file; reuse in every task):

```python
class CursorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.a.control_level=2
        self.inputs=ControllerInputs(self.a);self.s=Mk3Surface(self.a,self.inputs)
    def twin(self):
        # Same state, separate application, for "same as knob" comparisons.
        b=Application(self.tmp.name);b.control_level=self.a.control_level;b.page=self.a.page
        b.project=copy.deepcopy(self.a.project);return b,Mk3Surface(b,ControllerInputs(b))
    def press(self,name):self.s.button(name,True);self.s.button(name,False)
```

Known layouts (from the running code): `CHANNEL` page 0 = `['DEST.', None, 'LEVEL', 'pan', None, None, None, None]`; `GROOVE` = `['amount','cycle','invert', None×5]`; `MACRO` = 8 cells; channel path = `INPUT → CHANNEL 0..3 → GROOVE → MACRO`.

- [ ] **Step 1: Write the failing tests**

```python
def test_cursor_defaults_to_first_populated_cell(self):
    self.a.page='CHANNEL';self.a.channel_page=0
    self.assertEqual(self.s.cursor_cell(),0)
def test_cursor_snaps_to_nearest_populated_cell(self):
    self.a.page='CHANNEL';self.a.channel_page=0
    self.s.cursors[self.s.cursor_key()]=1          # empty cell between DEST. and LEVEL
    self.assertEqual(self.s.cursor_cell(),0)       # tie 0/2 → lower
    self.s.cursors[self.s.cursor_key()]=6
    self.assertEqual(self.s.cursor_cell(),3)
def test_no_cursor_outside_cursor_pages_or_on_plus(self):
    self.a.page='BROWSE';self.assertIsNone(self.s.cursor_cell())
    from app.plus_session import PlusSurface
    p=PlusSurface(self.a,self.inputs);self.a.page='CHANNEL';self.assertIsNone(p.cursor_cell())
def test_turn_edits_cursor_parameter_like_a_knob(self):
    self.a.page='CHANNEL';self.a.channel_page=0;self.s.cursors[self.s.cursor_key()]=2
    b,t=self.twin();t.rotate(3,1)
    self.s.master_turn(1);self.assertEqual(self.a.project,b.project)
def test_knob_turn_moves_cursor_but_empty_knob_does_not(self):
    self.a.page='CHANNEL';self.a.channel_page=0
    self.s.rotate(4,1);self.assertEqual(self.s.cursor_cell(),3)
    self.s.rotate(2,1);self.assertEqual(self.s.cursor_cell(),3)
def test_cursor_memory_per_layout(self):
    self.a.page='CHANNEL';self.a.channel_page=0;self.s.rotate(4,1)
    self.a.pad=5;self.assertEqual(self.s.cursor_cell(),3)               # other sound, same layout
    with patch.object(self.a,'plugin_selected',return_value={'uri':'urn:a'}), \
         patch.object(self.s,'fields',return_value=[Field('x',())]*8):
        self.a.page='PLUGIN';self.s.rotate(6,1);self.assertEqual(self.s.cursor_cell(),5)
    with patch.object(self.a,'plugin_selected',return_value={'uri':'urn:b'}), \
         patch.object(self.s,'fields',return_value=[Field('x',())]*8):
        self.assertEqual(self.s.cursor_cell(),0)                        # different plug-in
def test_shift_turn_moves_transport_and_leaves_parameters(self):
    self.a.page='CHANNEL';before=copy.deepcopy(self.a.project)
    self.a.shift=True;self.s.master_turn(1);self.a.shift=False
    self.assertGreater(self.a.clock_phase,0);self.assertEqual(before,self.a.project)
def test_master_modes_take_precedence(self):
    self.a.page='CHANNEL';tempo=self.a.project['tempo']
    self.press('TEMPO');self.s.master_turn(2);self.assertEqual(self.a.project['tempo'],tempo+2)
    # VOLUME and SWING: same pattern, asserting the master/swing value moved
    # exactly as Mk2Surface.rotate(0, 2) moves it on a twin with that mode latched.
def test_audio_loop_cursor_reaches_later_setting(self):
    self.a.track()['sample']='x.wav';self.a.audio_loop_setup()      # page 'AUDIO LOOP'; cells MODE, BARS, STRETCH, TUNE
    self.s.rotate(3,1);self.assertEqual(self.s.cursor_cell(),2)
    b,t=self.twin();t.rotate(3,1);self.s.master_turn(1);self.assertEqual(self.a.project,b.project)
```

(`Field` imports from `app.mk2_surface`. For VOLUME/SWING write the two analogous assertions explicitly; do not leave the comment.)

- [ ] **Step 2: Run to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_mk3_parameter_cursor -v`
Expected: errors — `AttributeError: 'Mk3Surface' object has no attribute 'cursor_cell'` / `'master_turn'`.

- [ ] **Step 3: Implement in `app/mk3_surface.py`**

- `__init__`: add `self.cursors={}`.
- `cursor_active`, `cursor_key`, `populated`, `cursor_cell` per Interfaces. `cursor_cell` resolves the stored index (default: first populated) to the nearest populated index, lower on a tie; it never writes `self.cursors`.
- `rotate(index, delta)`: before calling `super().rotate`, when `1 <= index <= 8`, `self.cursor_active()` and `self.fields()[index-1] is not None`, store `self.cursors[self.cursor_key()]=index-1`. Index 0 unchanged.
- `master_turn(delta)`: `cell=self.cursor_cell()`; if `cell is not None and not self.app.shift` → `self.rotate(cell+1, delta)`; else `self.rotate(0, delta)`. (`cursor_active()` already returns False under a master mode, so master modes fall through to `rotate(0, …)`.)

- [ ] **Step 4: Run to verify they pass**

Run: `/usr/bin/python3 -m unittest tests.test_mk3_parameter_cursor -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/mk3_surface.py tests/test_mk3_parameter_cursor.py
git commit -m "Add MK3 parameter cursor state and 4D turn editing"
```

---

### Task 2: 4D left/right moves the cursor across cells and pages

**Files:**
- Modify: `app/mk3_surface.py` (`Mk3Surface.button`: chain-slot handler around line 68; new method)
- Modify: `tests/test_mk3_chain_cards.py:30-31,34-39,53`
- Test: `tests/test_mk3_parameter_cursor.py`

**Interfaces:**
- Consumes: Task 1 `cursor_cell`, `cursor_key`, `populated`, `cursors`.
- Produces: `Mk3Surface.move_cursor(step: int) -> None` (`step` is −1 or +1).

- [ ] **Step 1: Write the failing tests**

```python
def test_right_moves_within_page_skipping_empty_cells(self):
    self.a.page='CHANNEL';self.a.channel_page=0
    self.press('MASTER RIGHT');self.assertEqual(self.s.cursor_cell(),2)
    self.press('MASTER RIGHT');self.assertEqual(self.s.cursor_cell(),3)
def test_right_past_last_cell_changes_page_and_lands_first(self):
    self.a.page='CHANNEL';self.a.channel_page=0;self.s.rotate(4,1)
    self.press('MASTER RIGHT');self.assertEqual((self.a.page,self.a.channel_page,self.s.cursor_cell()),('CHANNEL',1,0))
def test_left_before_first_cell_lands_on_last_of_previous_page(self):
    self.a.page='CHANNEL';self.a.channel_page=1
    self.press('MASTER LEFT');self.assertEqual((self.a.channel_page,self.s.cursor_cell()),(0,3))
def test_path_is_traversed_both_ways_and_stops_at_ends(self):
    self.a.page='INPUT';self.press('MASTER LEFT');self.assertEqual((self.a.page,self.s.cursor_cell()),('INPUT',0))
    for _ in range(40):self.press('MASTER RIGHT')
    self.assertEqual((self.a.page,self.s.cursor_cell()),('MACRO',7))
    for _ in range(40):self.press('MASTER LEFT')
    self.assertEqual((self.a.page,self.s.cursor_cell()),('INPUT',0))
def test_empty_views_are_skipped(self):
    # CHANNEL pages 1 and 2 report no fields; RIGHT from page 0's last cell lands on page 3.
def test_traversal_ending_on_empty_view_matches_page_buttons(self):
    # GROOVE and MACRO report no fields. From CHANNEL 3's last cell, RIGHT ends on MACRO
    # with cursor_cell() None. A twin pressing PAGE RIGHT twice from CHANNEL 3 has equal
    # page, channel_page, parameter_kind, parameter_choice, channel_field, groove_field,
    # macro_index and remembered control view (compare the attribute remember_control_view() writes).
def test_shift_left_right_keeps_old_behaviour(self):
    # On CHANNEL page 0 at cell 0, cell 3 and on page 3's last cell: SHIFT+RIGHT gives the
    # same state as a twin pressing MASTER RIGHT on a PlusSurface (old behaviour);
    # cursor and page unchanged by the cursor logic.
    # On SAMPLER with a plug-in: SHIFT+RIGHT selects PLUGIN slot 0.
def test_up_down_still_switch_slots_and_move_transport(self):
    # SAMPLER + one effect: MASTER DOWN → PLUGIN slot 0; MASTER UP → SAMPLER.
    # CHANNEL: MASTER DOWN advances clock_phase; project unchanged.
def test_empty_plugin_view_keeps_slot_switching(self):
    # Two effects with controls={} (fields all None): MASTER RIGHT → plugin_slot 1.
def test_held_right_moves_once(self):
    self.a.page='CHANNEL';self.a.channel_page=0
    self.s.button('MASTER RIGHT',True);self.s.button('MASTER RIGHT',True)
    self.assertEqual(self.s.cursor_cell(),2);self.s.button('MASTER RIGHT',False)
```

Empty views are simulated with `patch.object(self.s,'fields',side_effect=...)` returning `[None]*8` for the chosen `(page, channel_page)` and delegating to the real method otherwise. Write each commented test out in full with those exact assertions.

- [ ] **Step 2: Run to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_mk3_parameter_cursor -v`
Expected: the new tests FAIL (left/right still go to `NAV LEFT/RIGHT` / slot switching).

- [ ] **Step 3: Implement**

In `Mk3Surface.button`, before the existing chain-slot handler: if `name in ('MASTER LEFT','MASTER RIGHT')`, not `a.shift`, and `self.cursor_cell() is not None` → on press (guarded by `self.held` like the existing handlers: ignore if already held, add on press, discard on release) call `self.move_cursor(-1 or +1)`; return on both press and release. Everything else falls through unchanged, so SHIFT and empty views reach the old handlers.

`move_cursor(step)`: within `populated()`, move to the next index in `step` direction and store it. Past the end run the spec's bounded traversal:

```python
total=max(1,min(16,self.page_state()[1]))
for _ in range(total):
    key=self.cursor_key();self.change_page(step)
    if self.cursor_key()==key:return          # first/last page
    cells=self.populated() if self.cursor_active() else []
    if cells:self.cursors[self.cursor_key()]=cells[0] if step>0 else cells[-1];return
    total=max(1,min(16,self.page_state()[1]))
```

No rollback (spec: each step is an ordinary page change).

In `tests/test_mk3_chain_cards.py`: lines 30–31 use `MASTER DOWN` / `MASTER UP`; in `test_all_four_directions_select_slots_and_keep_audio_untouched` the `MASTER RIGHT` / `MASTER LEFT` presses (lines 34, 38–39) hold `SHIFT` (rename the test `..._slots_with_up_down_and_shift_left_right_...`); line 53 uses `MASTER DOWN`.

- [ ] **Step 4: Run to verify they pass**

Run: `/usr/bin/python3 -m unittest tests.test_mk3_parameter_cursor tests.test_mk3_chain_cards tests.test_mk3_ux tests.test_mk3_events_hold tests.test_event_range -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/mk3_surface.py tests/test_mk3_parameter_cursor.py tests/test_mk3_chain_cards.py
git commit -m "Move the MK3 parameter cursor with 4D left/right across pages"
```

---

### Task 3: Session wiring, snapshot and display marks

**Files:**
- Modify: `app/mk3_session.py` (`Mk3Session`: new `rotate_raw`; `update()` snapshot line ~108)
- Modify: `app/mk3_display.py:355-366` (parameter-cell loop)
- Test: `tests/test_mk3_parameter_cursor.py`

**Interfaces:**
- Consumes: Task 1 `master_turn`, `cursor_cell`.
- Produces: snapshot key `state['cursor']: int | None`; `Mk3Session.rotate_raw(index: int, delta: int) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
def session(self):
    from app.mk3_session import Mk3Session
    s=Mk3Session(self.tmp.name,self.a,self.inputs,{});self.addCleanup(s.close);return s
def test_session_routes_4d_turn_to_cursor(self):
    s=self.session();self.a.page='GROOVE';s.surface.cursors[s.surface.cursor_key()]=1
    b,t=self.twin();t.rotate(2,1);s.rotate_raw(0,1);self.assertEqual(self.a.project,b.project)
def test_batched_turn_moves_n_steps_and_clamps(self):
    # Discrete: CHANNEL cell 0 (DEST.) via rotate_raw(0,3) equals twin rotate(1,3); then
    # rotate_raw(0,-500) equals twin rotate(1,-500) (clamped at the first choice).
    # Continuous: CHANNEL cell 2 (LEVEL) via rotate_raw(0,5) / (0,-5) / (0,10**4) equals
    # twin rotate(3,±5) / rotate(3,10**4) (clamped at max).
def test_session_knobs_still_use_accumulator(self):
    s=self.session();self.a.page='CHANNEL';s.surface.rotate=Mock();s.rotate_raw(3,1)
    s.surface.rotate.assert_not_called()      # sub-quantum knob travel is accumulated, not applied
def test_snapshot_and_render_marks(self):
    # snapshot via mk3_state.snapshot + state['cursor']=cell, state['touches']=('KNOB 2 TOUCH',).
    # Render with Mk3Renderer().images(state). Cell i on the left screen spans x=i*120+5..+115.
    # cursor only (cell 0): pixel (60,269) == ACCENT, (60,219) != ACCENT.
    # touch only (cell 1): pixel (180,219) == ACCENT, (180,269) != ACCENT.
    # both on cell 2: (300,219) and (300,269) == ACCENT.
```

Write the commented tests out in full with exactly those assertions; `ACCENT` comes from the module `mk3_display` uses (resolve to RGB with the renderer's current scheme, as `test_mk3_themes` does).

- [ ] **Step 2: Run to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_mk3_parameter_cursor -v`
Expected: the new tests FAIL (`rotate_raw(0)` moves the transport; no cursor bar drawn).

- [ ] **Step 3: Implement**

- `Mk3Session.rotate_raw(index, delta)`: `if index==0: self.surface.master_turn(delta); return`; else `super().rotate_raw(index, delta)`.
- `Mk3Session.update`: after `state['touches']=…` add `state['cursor']=self.surface.cursor_cell()`.
- `mk3_display.py` cell loop: after the touch line, `if s.get('cursor')==side*4+i: c.rect(i*120+7,268,105,3,ACCENT)`.

- [ ] **Step 4: Run to verify they pass**

Run: `/usr/bin/python3 -m unittest tests.test_mk3_parameter_cursor tests.test_mk3_ux tests.test_mk3_chain_cards tests.test_mk3_themes -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add app/mk3_session.py app/mk3_display.py tests/test_mk3_parameter_cursor.py
git commit -m "Wire the 4D turn to the MK3 parameter cursor and draw its marker"
```

---

### Task 4: Documentation and full verification

**Files:**
- Modify: `docs/MK3_SUPPORT.md` (line 5 general controls; line 7 CHANNEL / PLUG-IN 4D slot text)

- [ ] **Step 1: Update the docs**

Line 5: add that on parameter pages (Pad, Channel, Sampler, Plug-in, Input, Groove, Macro, Audio Loop) one parameter is marked by a bar under its cell; turning the 4D encoder changes it one step per click; 4D left/right selects the previous/next parameter and continues onto the neighbouring page; turning a knob moves the mark to that knob; SHIFT + turn moves the playback position; SHIFT + left/right keeps the previous behaviour. Line 7: replace "push the 4D encoder left/up for the previous slot or right/down for the next" with "push the 4D encoder up for the previous slot or down for the next (or SHIFT + left/right)".

- [ ] **Step 2: Full suite**

Run: `/usr/bin/python3 -m unittest discover -s tests 2>&1 | grep -E "^(FAIL|ERROR):|^Ran|^FAILED|^OK"`
Expected: exactly the 7 known LV2 failures (`test_lv2_upload_native`, `test_export_audio` LV2, `test_lv2_engine` ×2, `test_master_midi_automation`, `test_presets` native group, `test_sample_memory` idle restart) and nothing else.

- [ ] **Step 3: Commit and push**

```bash
git add docs/MK3_SUPPORT.md
git commit -m "Document the MK3 4D parameter cursor"
git push origin mk3-4d-parameter-cursor
```

- [ ] **Step 4: Hardware acceptance (with the user)**

Run the branch on the MK3 (stop `machinista.service`, run `tools/run_desktop.sh` from this worktree with `REBUILD=1` the first time, or point the service at it). Check on Channel, Sampler, a plug-in with controls, Groove and Macro: turn, left/right including page changes, knob-turn follow, SHIFT + turn/left/right, up/down slot switching, and that the bar is visible.
