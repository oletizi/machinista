# MK3 4D-Encoder Parameter Cursor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the MK3, the 4D encoder edits one parameter at a time (a cursor over the eight knob cells): turn = one step, left/right = previous/next parameter.

**Architecture:** All state and logic live in `Mk3Surface` (`app/mk3_surface.py`). The physical 4D turn gets its own entry point, `master_turn()`, called from an `Mk3Session.rotate_raw` override; edits are delegated to the existing knob path `rotate(cell + 1, delta)`. The cursor is shown in the display snapshot and drawn as a bar under its cell.

**Tech Stack:** Python 3 (`unittest`), Pillow renderer (`app/mk3_display.py`).

**Spec:** `docs/superpowers/specs/2026-11-11-mk3-4d-parameter-cursor-design.md`

## Global Constraints

- MK3 only: every new behaviour is gated on `self.source == 'mk3'`; `PlusSurface` / `PlusSession` (source `'plus'`) must behave exactly as before.
- Cursor pages: `app.navigation.CONTROL_PAGES` (`PAD, SAMPLER, PLUGIN, CHANNEL, INPUT, GROOVE, MACRO`) plus `'AUDIO LOOP'`. Chain pages: `SAMPLER, PLUGIN, AUDIO LOOP`.
- View key: `(a.page, a.control_level, self.page_state()[0], uri)`; `uri` is `a.plugin_selected()['uri']` on `PLUGIN`, else `None`.
- Empty view (no populated cell): no cursor; 4D turn keeps current behaviour; left/right keep slot switching on chain pages and run page traversal on the other cursor pages.
- Traversal bound: `len(self.channel_page_path())` if that path is non-empty, else `self.page_state()[1]`; clamped to 1–32; also stop on an unchanged or already-visited view key. No rollback.
- Cursor is never saved to the project or settings.
- Display: touch line stays at y = 219 (2 px, above the cell); cursor bar at y = 268–270 (3 px, below the cell), `ACCENT`.
- Run tests with `/usr/bin/python3` (Homebrew python3 lacks Pillow). Baseline full suite: 7 LV2-fixture failures (6 failures + 1 error); nothing else may fail.

## Review Focus

1. Fast 4D spin → the session batches reports into `delta` = ±N; the parameter must move N steps and clamp, never wrap. (Task 3 `test_batched_turn_moves_n_steps_and_clamps`.)
2. Cursor on a cell that becomes empty after a slot/sound change → snaps to nearest populated cell, no exception. (Task 1 `test_cursor_snaps_to_nearest_populated_cell`.)
3. Plug-in page with no controls → no cursor; left/right still switch slots. (Task 2 `test_empty_plugin_view_keeps_slot_switching`.)
4. Holding the 4D left/right (repeated presses without release) → one move per physical press. (Task 2 `test_held_right_moves_once`.)
5. Turning the 4D while a master mode is latched → master value changes, cursor parameter untouched. (Task 1 `test_master_modes_take_precedence`.)

---

## Shared test fixture (`tests/test_mk3_parameter_cursor.py`)

Created in Task 1; later tasks add methods to the same class.

```python
import copy,tempfile,unittest
from unittest.mock import patch,Mock
from app.model import Application
from app.controller_inputs import ControllerInputs
from app.mk2_surface import Field
from app.mk3_surface import Mk3Surface

FULL=[Field('P%d'%i,'0',()) for i in range(8)]

class CursorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.a=Application(self.tmp.name);self.a.control_level=2
        self.inputs=ControllerInputs(self.a);self.s=Mk3Surface(self.a,self.inputs)
    def press(self,name,surface=None):
        s=surface or self.s;s.button(name,True);s.button(name,False)
    def same_as_knob(self,knob,delta,action):
        # Same application, same selectors: replay from an identical project.
        start=copy.deepcopy(self.a.project);self.s.rotate(knob,delta)
        expected=copy.deepcopy(self.a.project);self.a.project=copy.deepcopy(start)
        action();self.assertEqual(self.a.project,expected)
        return expected!=start
    def blank(self,*views):
        # views: (page, channel_page) pairs whose fields() report no parameters.
        real=self.s.fields
        def fake():
            a=self.a;key=(a.page,a.channel_page if a.page in ('CHANNEL','PAD') else 0)
            return [None]*8 if key in views else real()
        return patch.object(self.s,'fields',side_effect=fake)
```

Known layouts (from the running code, `control_level=2`): `INPUT` = `['SOURCE','GAIN',None×6]`; `CHANNEL` page 0 = `['DEST.',None,'LEVEL','pan',None×4]`, page 1 = `['aux1 dest','aux1 level','aux1 pre',None×5]`, page 3 = `['INTERNAL TO','EXT MIDI','note','channel',None×4]`; `GROOVE` = `['amount','cycle','invert',None×5]`; `MACRO` = 8 cells; `channel_page_path()` = `INPUT, CHANNEL 0..3, GROOVE, MACRO`.

---

### Task 1: Cursor state, knob tracking and `master_turn` in `Mk3Surface`

**Files:**
- Modify: `app/mk3_surface.py` (`Mk3Surface.__init__`, `rotate`; new methods)
- Test: `tests/test_mk3_parameter_cursor.py` (create, with the shared fixture)

**Interfaces:**
- Produces:
  - `Mk3Surface.cursors: dict` (view key → cell index 0–7)
  - `Mk3Surface.cursor_active() -> bool` — source `'mk3'`, page in cursor pages, `not self.master_mode`.
  - `Mk3Surface.cursor_key() -> tuple` — the view key.
  - `Mk3Surface.populated() -> list[int]` — indices of non-`None` entries of `self.fields()`.
  - `Mk3Surface.cursor_cell() -> int | None` — resolved cell; `None` if inactive or no populated cell. Never writes `cursors`.
  - `Mk3Surface.master_turn(delta: int) -> None` — physical 4D turn.

- [ ] **Step 1: Write the failing tests**

```python
    def test_cursor_defaults_to_first_populated_cell(self):
        self.a.page='CHANNEL';self.a.channel_page=0
        self.assertEqual(self.s.cursor_cell(),0)
    def test_cursor_snaps_to_nearest_populated_cell(self):
        self.a.page='CHANNEL';self.a.channel_page=0
        self.s.cursors[self.s.cursor_key()]=1;self.assertEqual(self.s.cursor_cell(),0)   # tie 0/2 → lower
        self.s.cursors[self.s.cursor_key()]=6;self.assertEqual(self.s.cursor_cell(),3)
    def test_no_cursor_outside_cursor_pages_or_on_plus(self):
        self.a.page='BROWSE';self.assertIsNone(self.s.cursor_cell())
        from app.plus_session import PlusSurface
        p=PlusSurface(self.a,self.inputs);self.a.page='CHANNEL';self.assertIsNone(p.cursor_cell())
    def test_turn_edits_cursor_parameter_like_a_knob(self):
        self.a.page='CHANNEL';self.a.channel_page=0
        self.assertTrue(self.same_as_knob(3,1,lambda:self.s.master_turn(1)))      # LEVEL
        self.assertTrue(self.same_as_knob(1,1,lambda:self.s.master_turn(1)))      # DEST.
    def test_knob_turn_moves_cursor_but_empty_knob_does_not(self):
        self.a.page='CHANNEL';self.a.channel_page=0
        self.s.rotate(4,1);self.assertEqual(self.s.cursor_cell(),3)
        self.s.rotate(2,1);self.assertEqual(self.s.cursor_cell(),3)
    def test_cursor_memory_per_layout(self):
        self.a.page='CHANNEL';self.a.channel_page=0;self.s.rotate(4,1)
        self.a.pad=5;self.assertEqual(self.s.cursor_cell(),3)
        with patch.object(self.s,'fields',return_value=FULL), patch.object(self.s,'page_state',return_value=(0,1)):
            self.a.page='PLUGIN'
            with patch.object(self.a,'plugin_selected',return_value={'uri':'urn:a'}):
                self.s.cursors[self.s.cursor_key()]=5;self.assertEqual(self.s.cursor_cell(),5)
            with patch.object(self.a,'plugin_selected',return_value={'uri':'urn:b'}):
                self.assertEqual(self.s.cursor_cell(),0)
    def test_shift_turn_moves_transport_and_leaves_parameters(self):
        self.a.page='CHANNEL';before=copy.deepcopy(self.a.project)
        self.a.shift=True;self.s.master_turn(1);self.a.shift=False
        self.assertGreater(self.a.clock_phase,0);self.assertEqual(before,self.a.project)
    def test_master_modes_take_precedence(self):
        self.a.page='CHANNEL';self.s.cursors[self.s.cursor_key()]=2
        for mode in ('TEMPO','SWING','VOLUME'):
            with self.subTest(mode=mode):
                self.press(mode);start=copy.deepcopy(self.a.project)
                self.s.rotate(0,2);expected=copy.deepcopy(self.a.project)
                self.a.project=copy.deepcopy(start);self.s.master_turn(2)
                self.assertEqual(self.a.project,expected);self.assertNotEqual(expected,start)
                self.press(mode)                                                 # unlatch
    def test_audio_loop_cursor_reaches_later_setting(self):
        self.a.track()['sample']='x.wav';self.a.audio_loop_setup()               # MODE, BARS, STRETCH, TUNE
        self.assertTrue(self.same_as_knob(2,1,lambda:self.s.master_turn(1)))      # BARS
        self.assertEqual(self.s.cursor_cell(),1)
```

If pressing a master-mode button a second time does not unlatch it in the running code, unlatch by setting `self.s.master_mode=None` instead; do not weaken the assertions.

- [ ] **Step 2: Run to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_mk3_parameter_cursor -v`
Expected: errors — `AttributeError: 'Mk3Surface' object has no attribute 'cursor_cell'` / `'master_turn'`.

- [ ] **Step 3: Implement in `app/mk3_surface.py`**

- `__init__`: add `self.cursors={}`.
- `cursor_active`, `cursor_key`, `populated`, `cursor_cell` per Interfaces. `cursor_cell` resolves the stored index (default: first populated) to the nearest populated index, lower on a tie.
- `rotate(index, delta)`: before calling `super().rotate`, when `1 <= index <= 8`, `self.cursor_active()` and `self.fields()[index-1] is not None`, store `self.cursors[self.cursor_key()]=index-1`. Index 0 unchanged.
- `master_turn(delta)`: `cell=self.cursor_cell()`; if `cell is not None and not self.app.shift` → `self.rotate(cell+1, delta)`; else `self.rotate(0, delta)`.

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
- Modify: `app/mk3_surface.py` (`Mk3Surface.button`, before the chain-slot handler at line 68; new method)
- Modify: `tests/test_mk3_chain_cards.py:30-31,34-39,53`
- Test: `tests/test_mk3_parameter_cursor.py`

**Interfaces:**
- Consumes: Task 1 `cursor_cell`, `cursor_key`, `cursor_active`, `populated`, `cursors`.
- Produces: `Mk3Surface.move_cursor(step: int) -> None` (`step` is −1 or +1).

- [ ] **Step 1: Write the failing tests**

```python
    def view(self):return (self.a.page,self.a.channel_page,self.s.cursor_cell())
    def test_right_moves_within_page_skipping_empty_cells(self):
        self.a.page='CHANNEL';self.a.channel_page=0
        self.press('MASTER RIGHT');self.assertEqual(self.s.cursor_cell(),2)
        self.press('MASTER RIGHT');self.assertEqual(self.s.cursor_cell(),3)
    def test_right_past_last_cell_changes_page_and_lands_first(self):
        self.a.page='CHANNEL';self.a.channel_page=0;self.s.rotate(4,1)
        self.press('MASTER RIGHT');self.assertEqual(self.view(),('CHANNEL',1,0))
    def test_left_before_first_cell_lands_on_last_of_previous_page(self):
        self.a.page='CHANNEL';self.a.channel_page=1
        self.press('MASTER LEFT');self.assertEqual(self.view(),('CHANNEL',0,3))
    def test_path_is_traversed_both_ways_and_stops_at_ends(self):
        self.a.page='INPUT';self.press('MASTER LEFT');self.assertEqual((self.a.page,self.s.cursor_cell()),('INPUT',0))
        for _ in range(40):self.press('MASTER RIGHT')
        self.assertEqual((self.a.page,self.s.cursor_cell()),('MACRO',7))
        for _ in range(40):self.press('MASTER LEFT')
        self.assertEqual((self.a.page,self.s.cursor_cell()),('INPUT',0))
    def test_consecutive_empty_views_are_skipped_from_input_and_groove(self):
        with self.blank(('CHANNEL',0),('CHANNEL',1),('CHANNEL',2),('CHANNEL',3)):
            self.a.page='INPUT';self.s.rotate(2,1)                                # GAIN, last cell
            self.press('MASTER RIGHT');self.assertEqual((self.a.page,self.s.cursor_cell()),('GROOVE',0))
            self.press('MASTER LEFT');self.assertEqual((self.a.page,self.s.cursor_cell()),('INPUT',1))
    def test_empty_endpoint_matches_page_buttons_and_can_be_left(self):
        with self.blank(('GROOVE',0),('MACRO',0)):
            self.a.page='CHANNEL';self.a.channel_page=3;self.s.rotate(4,1)
            self.press('MASTER RIGHT')
            b=Application(self.tmp.name);b.control_level=2;b.page='CHANNEL';b.channel_page=3
            t=Mk3Surface(b,ControllerInputs(b));t.change_page(1);t.change_page(1)
            keys=('page','channel_page','parameter_kind','parameter_choice','channel_field','groove_field','macro_index','control_views')
            self.assertEqual({k:getattr(self.a,k) for k in keys},{k:getattr(b,k) for k in keys})
            self.assertIsNone(self.s.cursor_cell())
            self.press('MASTER LEFT');self.assertEqual(self.view(),('CHANNEL',3,3))
    def test_shift_left_right_keeps_old_behaviour(self):
        from app.plus_session import PlusSurface
        for page,channel_page,knob in (('CHANNEL',0,1),('CHANNEL',0,4),('CHANNEL',3,4)):
            with self.subTest(page=page,cell=knob-1):
                b=Application(self.tmp.name);b.control_level=2;b.page=page;b.channel_page=channel_page
                old=PlusSurface(b,ControllerInputs(b))
                self.a.page=page;self.a.channel_page=channel_page;self.s.cursors[self.s.cursor_key()]=knob-1
                self.a.shift=b.shift=True;self.press('MASTER RIGHT');self.press('MASTER RIGHT',old);self.a.shift=b.shift=False
                self.assertEqual((self.a.page,self.a.channel_page,self.a.project),(b.page,b.channel_page,b.project))
                self.assertEqual(self.s.cursor_cell(),knob-1)
        self.a.track()['sample']='x.wav';self.a.track()['plugins']=[dict(uri='urn:filter',kind='EFFECT',controls={})]
        self.a.page='SAMPLER';self.a.shift=True;self.press('MASTER RIGHT');self.a.shift=False
        self.assertEqual((self.a.page,self.a.plugin_slot),('PLUGIN',0))
    def test_up_down_still_switch_slots_and_move_transport(self):
        self.a.track()['sample']='x.wav';self.a.track()['plugins']=[dict(uri='urn:filter',kind='EFFECT',controls={})]
        self.a.page='SAMPLER';self.press('MASTER DOWN');self.assertEqual((self.a.page,self.a.plugin_slot),('PLUGIN',0))
        self.press('MASTER UP');self.assertEqual(self.a.page,'SAMPLER')
        self.a.page='CHANNEL';before=copy.deepcopy(self.a.project)
        self.press('MASTER DOWN');self.assertGreater(self.a.clock_phase,0);self.assertEqual(before,self.a.project)
    def test_empty_plugin_view_keeps_slot_switching(self):
        self.a.track()['plugins']=[dict(uri='urn:filter',kind='EFFECT',controls={}),dict(uri='urn:delay',kind='EFFECT',controls={})]
        self.press('PLUG-IN');self.assertEqual(self.a.page,'PLUGIN');self.assertIsNone(self.s.cursor_cell())
        self.press('MASTER RIGHT');self.assertEqual(self.a.plugin_slot,1)
    def test_held_right_moves_once(self):
        self.a.page='CHANNEL';self.a.channel_page=0
        self.s.button('MASTER RIGHT',True);self.s.button('MASTER RIGHT',True)
        self.assertEqual(self.s.cursor_cell(),2);self.s.button('MASTER RIGHT',False)
```

`control_views` is the attribute `remember_control_view()` writes (`app/navigation.py:28-31`).

- [ ] **Step 2: Run to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_mk3_parameter_cursor -v`
Expected: the new tests FAIL (left/right still map to `NAV LEFT/RIGHT` / slot switching).

- [ ] **Step 3: Implement**

In `Mk3Surface.button`, before the existing chain-slot handler, intercept `MASTER LEFT` / `MASTER RIGHT` when `not a.shift`, `self.cursor_active()`, and either `self.cursor_cell() is not None` or `a.page` is not a chain page. Use the `self.held` guard like the neighbouring handlers (ignore a press already held; add on press; discard on release); call `self.move_cursor(-1 or +1)` on press; return on press and release. Everything else falls through unchanged.

`move_cursor(step)`: if there is a cursor cell and a populated cell beyond it in `step` direction, store that cell and return. Otherwise run the bounded traversal:

```python
path=self.channel_page_path()
bound=max(1,min(32,len(path) if path else self.page_state()[1]))
seen={self.cursor_key()}
for _ in range(bound):
    self.change_page(step);key=self.cursor_key()
    if key in seen:return                     # first/last page or cycle
    seen.add(key)
    cells=self.populated() if self.cursor_active() else []
    if cells:self.cursors[key]=cells[0] if step>0 else cells[-1];return
```

In `tests/test_mk3_chain_cards.py`: lines 30–31 use `MASTER DOWN` / `MASTER UP`; in `test_all_four_directions_select_slots_and_keep_audio_untouched`, wrap the `MASTER RIGHT` / `MASTER LEFT` presses (lines 34, 38–39) in `self.a.shift=True … False` and rename it `test_up_down_and_shift_left_right_select_slots_and_keep_audio_untouched`; line 53 uses `MASTER DOWN`.

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
- Consumes: Task 1 `master_turn`, `cursor_cell`, `cursors`, `cursor_key`.
- Produces: snapshot key `state['cursor']: int | None`; `Mk3Session.rotate_raw(index: int, delta: int) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
    def session(self,cls=None):
        from app.mk3_session import Mk3Session
        s=(cls or Mk3Session)(self.tmp.name,self.a,self.inputs,{});self.addCleanup(s.close)
        self.s=s.surface;return s
    def test_session_routes_4d_turn_to_cursor(self):
        s=self.session();self.a.page='GROOVE'
        self.assertTrue(self.same_as_knob(2,1,lambda:s.rotate_raw(0,1)))         # cycle
    def test_batched_turn_moves_n_steps_and_clamps(self):
        s=self.session();self.a.page='CHANNEL';self.a.channel_page=0
        for knob,delta in ((1,3),(1,-500),(3,5),(3,-5),(3,10**4)):
            with self.subTest(knob=knob,delta=delta):
                self.same_as_knob(knob,delta,lambda:s.rotate_raw(0,delta))
    def test_session_knobs_still_use_accumulator(self):
        s=self.session();self.a.page='CHANNEL';s.surface.rotate=Mock();s.rotate_raw(3,1)
        s.surface.rotate.assert_not_called()
    def test_plus_session_4d_turn_keeps_transport(self):
        from app.plus_session import PlusSession
        s=self.session(PlusSession);self.a.page='CHANNEL';before=copy.deepcopy(self.a.project)
        s.rotate_raw(0,1);self.assertGreater(self.a.clock_phase,0);self.assertEqual(before,self.a.project)
    def test_snapshot_and_render_marks(self):
        from app.mk3_state import snapshot
        from app.mk3_display import Mk3Renderer
        r=Mk3Renderer();self.addCleanup(r.close)
        self.a.settings['controllers']['mk3']['color_scheme']='current';self.a.page='MACRO'
        base=snapshot(self.s);base['touches']=();base['cursor']=None
        def render(**changes):return r.images(dict(base,**changes))[0]
        plain=render();cursor=render(cursor=0);touch=render(touches=('KNOB 2 TOUCH',));both=render(cursor=2,touches=('KNOB 3 TOUCH',))
        px=lambda img,x,y:img.getpixel((x,y))
        self.assertNotEqual(px(cursor,60,269),px(plain,60,269));self.assertEqual(px(cursor,60,219),px(plain,60,219))
        self.assertNotEqual(px(touch,180,219),px(plain,180,219));self.assertEqual(px(touch,180,269),px(plain,180,269))
        self.assertNotEqual(px(both,300,219),px(plain,300,219));self.assertNotEqual(px(both,300,269),px(plain,300,269))
        session=self.session();self.a.page='MACRO';session.surface.cursors[session.surface.cursor_key()]=4
        captured={}
        session.output=Mock(submit=lambda state:captured.update(state),submit_leds=lambda *_:None)
        session.next_led=session.next_frame=0;session.update(1)
        self.assertEqual(captured['cursor'],4)
```

- [ ] **Step 2: Run to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_mk3_parameter_cursor -v`
Expected: the new tests FAIL (`rotate_raw(0)` moves the transport; no cursor bar; no `cursor` in the snapshot).

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

Run the branch on the MK3 (stop `machinista.service`, run `tools/run_desktop.sh` from this worktree with `REBUILD=1` the first time). Check on Channel, Sampler, a plug-in with controls, Groove and Macro: turn, left/right including page changes, knob-turn follow, SHIFT + turn/left/right, up/down slot switching, and that the bar is visible.
