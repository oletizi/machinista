# MK3 Controller Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the MK3's 4D-encoder and knob behaviour selectable through declarative JSON profiles, with built-in "Original" (pre-cursor behaviour) and "4D cursor" profiles.

**Architecture:** A pure loader/validator/matcher (`app/controller_profiles.py`) turns JSON files into immutable `Profile` objects. The MK3 surface matches a profile once per physical event, at new `physical_*` delivery hooks, and runs a fixed action from `app/mk3_actions.py`. The original surface path (`button`, `rotate`) is restored to its pre-cursor form and never consults a profile.

**Tech Stack:** Python 3 stdlib only (`json`, `re`, `dataclasses`, `pathlib`, `os`, `stat`), `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-11-mk3-controller-profiles-design.md` (read it; this plan argues from it). The cursor behaviour itself is specified in `docs/superpowers/specs/2026-11-11-mk3-4d-parameter-cursor-design.md`.

## Global Constraints

- Profiles are data only: nothing in a profile file is ever executed, imported or `eval`ed.
- Python stdlib only; no new dependencies. Run tests with `/usr/bin/python3 -m unittest` from the repo root.
- `format` must be exactly `1`; `device` must be `"mk3"`; `name` 1–24 chars; at most 64 bindings; user files at most 65536 bytes; identifier = file stem matching `[a-z0-9][a-z0-9-]{0,31}`.
- Built-in identifiers: `original` (name `Original`, no bindings, defined in code) and `cursor` (name `4D cursor`, `app/controller_profiles_data/cursor.json`).
- User folder: `Path(app.root)/'controller-profiles'`.
- Setting: `app.settings['controllers']['mk3']['profile']`, default `'original'`. Plus/other devices get no `profile` key.
- Messages (exact): `PROFILE NOT FOUND`, `PROFILE ERROR`.
- Original handling = `Mk3Surface.button` / `Mk3Surface.rotate` as at commit `cebddb3` plus later non-cursor changes. They must never consult a profile.
- Profiles are consulted only when `surface.source=='mk3'` and `cursor_active()` (parameter page, no master mode) and the update lock is not active.
- Known test baseline with the native build: 7 LV2 fixture failures (6 failures + 1 error) in `test_lv2_upload_native`, `test_export_audio`, `test_lv2_engine` (2), `test_master_midi_automation`, `test_presets`, `test_sample_memory`. Anything else failing is a regression.
- Commit identity is repo-local (already configured). End each commit message with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01Nu4TBQLGDFhpdgTys4CfWA
  ```

## Review Focus

1. **Update lock.** During an update (`time.monotonic() < app.update_lock_until`), a profile action must do nothing, exactly as the original handlers ignore input then. Test: Task 2, `test_update_lock_blocks_profile_actions`.
2. **Repeated press reports.** The MK3 can report a press again before its release; a profile action must run once per press. Test: Task 2, `test_held_right_moves_once` (existing, via the physical hook), and `test_repeat_press_while_owned_runs_once`.
3. **Original is transparent through the hooks.** With `original` selected, every intercepted input delivered through `physical_*` must give exactly the state that calling `button`/`rotate` directly gives, with SHIFT up and down. Test: Task 2, `test_original_profile_is_transparent`.
4. **Hostile or odd user files.** A UTF-8 BOM, invalid UTF-8, a directory named `x.json`, a symlink, or a 1 MB file must be skipped with a journal line and must never stop loading of the others. Test: Task 1, `test_loader_skips_bad_files_and_keeps_good_ones`.
5. **Profile edited while selected.** Re-opening the settings page reloads files; if the selected profile became invalid, the controller falls back to Original once with `PROFILE NOT FOUND` and recovers when the file is fixed. Test: Task 3, `test_invalid_selected_profile_falls_back_and_recovers`.

---

### Task 1: Profile loader, validator and matcher

**Files:**
- Create: `app/controller_profiles.py`
- Create: `app/controller_profiles_data/cursor.json`
- Test: `tests/test_controller_profiles.py`

**Interfaces:**
- Produces:
  - Constants: `INPUTS = ('4D TURN','4D UP','4D DOWN','4D LEFT','4D RIGHT','4D PUSH','KNOB TURN','KNOB TOUCH')`; `GROUPS = {'parameters': ('PAD','SAMPLER','PLUGIN','CHANNEL','INPUT','GROOVE','MACRO','AUDIO LOOP'), 'chain': ('SAMPLER','PLUGIN','AUDIO LOOP')}`; `ACTIONS: dict[str, frozenset[str]]` (input → valid actions, each including `default` and `none`); `BUILTIN_DIR = Path(__file__).parent/'controller_profiles_data'`.
  - `class ProfileError(ValueError)`.
  - `@dataclass(frozen=True) class Binding: index:int; input:str; action:str; pages:frozenset[str]; shift:bool|None; cursor:bool|None` (`pages` always expanded, never empty; omitted → all of `GROUPS['parameters']`).
  - `@dataclass(frozen=True) class Profile: ident:str; name:str; bindings:tuple[Binding,...]` with
    - `match(self, input:str, page:str, shift:bool, cursor:bool) -> Binding|None` — first binding in order whose input equals and whose conditions hold.
    - `shows_cursor(self, page:str) -> bool` — True if some binding has an action starting with `cursor.` and `page in pages` and `cursor` condition is `None` or `True`.
  - `ORIGINAL = Profile('original','Original',())`.
  - `validate(ident:str, data:object) -> Profile` raising `ProfileError(reason)`.
  - `class ProfileStore: __init__(self, user_dir:Path, builtin_dir:Path=BUILTIN_DIR)`; `load(self) -> None` (never raises; fills `self.profiles: dict[str,Profile]` in order original, built-ins sorted by ident, user profiles sorted by ident, and `self.errors: list[str]`); `get(self, ident:str) -> Profile|None`; `ids(self) -> list[str]`.

Action sets (exact):
- `4D TURN`: `cursor.edit`, `transport.move`, `edit.knob1` … `edit.knob8`
- `4D UP/DOWN/LEFT/RIGHT/PUSH`: `cursor.previous`, `cursor.next`, `page.previous`, `page.next`, `chain.previous`, `chain.next`, `transport.back`, `transport.forward`
- `KNOB TURN`, `KNOB TOUCH`: `cursor.follow`
- every input additionally: `default`, `none`

- [ ] **Step 1: Write `tests/test_controller_profiles.py` (failing)**

Helpers and tests (names and assertions are the contract; write them in the repo's compact style):

```python
import json,os,tempfile,unittest
from pathlib import Path
from app.controller_profiles import (validate,ProfileError,ProfileStore,ORIGINAL,GROUPS,INPUTS,ACTIONS,BUILTIN_DIR)

def doc(*bindings,**top):
    d={'format':1,'name':'Test','device':'mk3','bindings':list(bindings)};d.update(top);return d

class ValidateTests(unittest.TestCase):
    def test_minimal_valid_profile(self):
        p=validate('mine',doc());self.assertEqual((p.ident,p.name,p.bindings),('mine','Test',()))
    def test_binding_defaults_expand_to_parameter_pages(self):
        b=validate('x',doc({'input':'4D TURN','action':'cursor.edit'})).bindings[0]
        self.assertEqual((b.index,b.pages,b.shift,b.cursor),(0,frozenset(GROUPS['parameters']),None,None))
    def test_pages_accept_name_group_and_mixed_list(self):
        for pages,expected in (('MACRO',{'MACRO'}),('chain',set(GROUPS['chain'])),(['MACRO','chain'],{'MACRO',*GROUPS['chain']})):
            with self.subTest(pages=pages):
                b=validate('x',doc({'input':'4D LEFT','action':'page.next','pages':pages})).bindings[0]
                self.assertEqual(b.pages,frozenset(expected))
    def test_rejections(self):
        cases={
          'format 2 says newer':(doc(format=2),'newer Machinista'),
          'format bool':(doc(format=True),'format'),
          'device':(doc(device='mk2'),'device'),
          'unknown top key':(doc(extra=1),'extra'),
          'empty name':(doc(name=''),'name'),
          'long name':(doc(name='x'*25),'name'),
          'bindings not list':(doc(bindings={}),'bindings'),
          'too many':(doc(*[{'input':'4D TURN','action':'none'}]*65),'64'),
          'unknown input':(doc({'input':'4D SPIN','action':'none'}),"unknown input '4D SPIN'"),
          'unknown action':(doc({'input':'4D TURN','action':'cursor.nxt'}),"unknown action 'cursor.nxt' (misspelt, or added in a newer Machinista)"),
          'action wrong input':(doc({'input':'4D TURN','action':'cursor.next'}),'not valid for 4D TURN'),
          'unknown binding key':(doc({'input':'4D TURN','action':'none','when':1}),'when'),
          'bad page':(doc({'input':'4D TURN','action':'none','pages':'BROWSE'}),'BROWSE'),
          'bad group in list':(doc({'input':'4D TURN','action':'none','pages':['MACRO','chains']}),'chains'),
          'empty pages list':(doc({'input':'4D TURN','action':'none','pages':[]}),'pages'),
          'shift not bool':(doc({'input':'4D TURN','action':'none','shift':1}),'shift'),
          'cursor not bool':(doc({'input':'4D TURN','action':'none','cursor':'yes'}),'cursor'),
          'binding not object':(doc('4D TURN'),'binding 0'),
          'not an object':([], 'object'),
        }
        for label,(data,fragment) in cases.items():
            with self.subTest(label):
                with self.assertRaises(ProfileError) as e:validate('x',data)
                self.assertIn(fragment,str(e.exception))
    def test_note_fields_are_ignored(self):
        validate('x',doc({'input':'4D TURN','action':'none','note':'n'},note='top'))

class MatchTests(unittest.TestCase):
    def test_first_match_wins_in_file_order(self):
        broad={'input':'4D LEFT','action':'page.previous'};narrow={'input':'4D LEFT','action':'cursor.previous','pages':'MACRO'}
        self.assertEqual(validate('a',doc(broad,narrow)).match('4D LEFT','MACRO',False,True).action,'page.previous')
        self.assertEqual(validate('b',doc(narrow,broad)).match('4D LEFT','MACRO',False,True).action,'cursor.previous')
        self.assertEqual(validate('b',doc(narrow,broad)).match('4D LEFT','GROOVE',False,True).action,'page.previous')
    def test_conditions(self):
        p=validate('x',doc({'input':'4D TURN','action':'cursor.edit','shift':False,'cursor':True}))
        self.assertIsNotNone(p.match('4D TURN','CHANNEL',False,True))
        self.assertIsNone(p.match('4D TURN','CHANNEL',True,True))
        self.assertIsNone(p.match('4D TURN','CHANNEL',False,False))
        self.assertIsNone(p.match('4D LEFT','CHANNEL',False,True))
        self.assertIsNone(p.match('4D TURN','BROWSE',False,True))
    def test_omitted_conditions_match_either_value(self):
        p=validate('x',doc({'input':'4D PUSH','action':'page.next'}))
        for shift in (False,True):
            for cursor in (False,True):self.assertIsNotNone(p.match('4D PUSH','GROOVE',shift,cursor))
    def test_shows_cursor(self):
        p=validate('x',doc({'input':'4D TURN','action':'cursor.edit','pages':'MACRO','shift':True},{'input':'4D LEFT','action':'page.next'}))
        self.assertTrue(p.shows_cursor('MACRO'));self.assertFalse(p.shows_cursor('GROOVE'))
        self.assertFalse(validate('y',doc({'input':'4D TURN','action':'cursor.edit','cursor':False})).shows_cursor('MACRO'))
        self.assertFalse(ORIGINAL.shows_cursor('MACRO'))

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.dir=Path(self.tmp.name)/'controller-profiles'
    def write(self,name,data):
        self.dir.mkdir(exist_ok=True);path=self.dir/name
        path.write_bytes(data if isinstance(data,bytes) else json.dumps(data).encode());return path
    def test_builtins_validate_and_order(self):
        s=ProfileStore(self.dir);s.load()
        self.assertEqual(s.ids(),['original','cursor']);self.assertEqual(s.errors,[])
        self.assertEqual(s.get('cursor').name,'4D cursor');self.assertIs(s.get('original'),ORIGINAL)
    def test_missing_user_folder_is_fine(self):
        s=ProfileStore(self.dir);s.load();self.assertEqual(s.errors,[])
    def test_loader_skips_bad_files_and_keeps_good_ones(self):
        self.write('zeta.json',doc(name='Zeta'));self.write('alpha.json',doc(name='Alpha'))
        self.write('bad-json.json',b'{');self.write('bom.json',b'\xef\xbb\xbf'+json.dumps(doc()).encode())
        self.write('latin.json',b'{"name":"\xff"}');self.write('Upper.json',doc());self.write('cursor.json',doc())
        self.write('big.json',b' '*65537);(self.dir/'dir.json').mkdir()
        os.symlink(self.dir/'alpha.json',self.dir/'link.json');self.write('notes.txt',b'x')
        s=ProfileStore(self.dir);s.load()
        self.assertEqual(s.ids(),['original','cursor','alpha','zeta'])
        joined='\n'.join(s.errors)
        for name in ('bad-json.json','bom.json','latin.json','Upper.json','cursor.json','big.json','dir.json','link.json'):
            self.assertIn(name,joined)
        self.assertNotIn('notes.txt',joined)
    def test_reload_picks_up_changes(self):
        s=ProfileStore(self.dir);s.load();self.write('mine.json',doc());s.load();self.assertIn('mine',s.ids())
        (self.dir/'mine.json').write_text('{');s.load();self.assertNotIn('mine',s.ids())
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `/usr/bin/python3 -m unittest tests.test_controller_profiles -v`
Expected: ERROR, `ModuleNotFoundError: No module named 'app.controller_profiles'`.

- [ ] **Step 3: Create `app/controller_profiles_data/cursor.json`**

Exactly the spec's 4D cursor profile:

```json
{
  "format": 1,
  "name": "4D cursor",
  "device": "mk3",
  "note": "4D turn edits the parameter under the cursor; left/right move it.",
  "bindings": [
    {"input": "4D TURN",  "shift": false, "cursor": true, "action": "cursor.edit"},
    {"input": "4D LEFT",  "shift": false, "cursor": true, "action": "cursor.previous"},
    {"input": "4D RIGHT", "shift": false, "cursor": true, "action": "cursor.next"},
    {"input": "4D LEFT",  "pages": ["PAD","CHANNEL","INPUT","GROOVE","MACRO"], "shift": false, "action": "cursor.previous"},
    {"input": "4D RIGHT", "pages": ["PAD","CHANNEL","INPUT","GROOVE","MACRO"], "shift": false, "action": "cursor.next"},
    {"input": "KNOB TURN", "action": "cursor.follow"}
  ]
}
```

- [ ] **Step 4: Implement `app/controller_profiles.py`**

Module docstring states that profiles are data only and never executed. No imports from `app.*`. Rules:
- `validate`: top level must be a `dict` (else `'profile must be a JSON object'`); allowed top keys `format,name,device,bindings,note`; `format` must be `int` and not `bool`; `format>1` → `'format N needs a newer Machinista'`; every reason for a binding starts with `'binding <index>: '`. Unknown input/action/page/group messages use the exact wording in the test.
- `ProfileStore.load`: iterate `sorted(user_dir.glob('*.json'))` when the folder exists; for each: `os.lstat`; skip with an error unless `stat.S_ISREG` (symlinks and directories fail this); skip if `st_size>65536`; skip if the stem fails the identifier pattern or equals a built-in identifier; read bytes, decode `'utf-8'` (strict; a BOM therefore fails JSON parsing), `json.loads`, `validate`. Each error string is `f'{path.name}: {reason}'` and is also `print(f'controller profile skipped: {error}', flush=True)`. Catch `(OSError, UnicodeError, ValueError)` around each file (`ProfileError` and `json.JSONDecodeError` are `ValueError`s). Built-ins load from `builtin_dir` with the same validator; a built-in failure raises (it is a bug, and the test proves none fail).

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `/usr/bin/python3 -m unittest tests.test_controller_profiles -v`
Expected: all OK.

- [ ] **Step 6: Commit**

```bash
git add app/controller_profiles.py app/controller_profiles_data/cursor.json tests/test_controller_profiles.py
git commit -m "Add MK3 controller profile loader, validator and matcher"
```

---

### Task 2: Physical dispatch, actions and the restored original path

**Files:**
- Create: `app/mk3_actions.py`
- Modify: `app/mk3_surface.py` (cursor interception out, dispatch in)
- Modify: `app/mk2_surface.py` (pass-through `physical_button`, `physical_rotate`)
- Modify: `app/mk2_session.py:119,140,157` (deliver through `physical_*`)
- Modify: `app/mk3_session.py` (`rotate_raw(0)` → `physical_turn`)
- Modify: `app/controller_settings.py` (`profile` default and type check; `app.controller_profiles` store)
- Restore: `tests/test_mk3_chain_cards.py` from `cebddb3`
- Modify: `tests/test_mk3_parameter_cursor.py` (select the cursor profile; physical entry points)
- Test: `tests/test_mk3_controller_profiles.py` (create)

**Interfaces:**
- Consumes (Task 1): `ProfileStore`, `ORIGINAL`, `Profile.match`, `Binding.action/.index`.
- Produces:
  - `Mk2Surface.physical_button(self,name,pressed)` → `self.button(name,pressed)`; `Mk2Surface.physical_rotate(self,index,delta)` → `self.rotate(index,delta)`.
  - `Mk3Surface.physical_turn(self,delta)`, `physical_button(self,name,pressed)`, `physical_rotate(self,index,delta)`, `active_profile(self) -> Profile`, `dispatch(self,input,index,delta) -> str` (`'profile'|'original'`), `self.press_owner: dict[str,str]`, `switch_chain(self,step:int) -> bool`.
  - `app/mk3_actions.py`: `class CursorState` mixin (moved from `Mk3Surface`, unchanged behaviour): `cursors`, `cursor_active()`, `cursor_key()`, `populated()`, `cursor_cell()`, `move_cursor(step)`; and `run(surface, action:str, index:int|None, delta:int) -> bool` (True = acted, False = not applicable or `cursor.follow` continuing).
  - `app.controller_profiles` (a loaded `ProfileStore` on the `Application`), created in `init_controller_settings`.
  - `app.settings['controllers']['mk3']['profile']` (default `'original'`).

- [ ] **Step 1: Restore the pre-cursor chain-card test and adapt the cursor tests**

```bash
git checkout cebddb3 -- tests/test_mk3_chain_cards.py
```

In `tests/test_mk3_parameter_cursor.py` make only these changes (assertions stay unchanged):
- `setUp`: after creating `self.a`, add `self.a.settings['controllers']['mk3']['profile']='cursor'`.
- `press()`: `s.physical_button(name,True);s.physical_button(name,False)`.
- Every `master_turn(` → `physical_turn(`.
- Every direct `s.button(` / `self.s.button(` call → `physical_button(`.
- Knob turns meant to move the cursor → `physical_rotate`: `self.s.rotate(4,1)` (three occurrences) and `self.s.rotate(2,1)` (two occurrences). Keep `self.s.rotate(knob,delta)` in `same_as_knob` and `self.s.rotate(0,2)` in `test_master_modes_take_precedence`: they are the non-dispatching reference.
- `test_session_knobs_still_use_accumulator`: mock `physical_rotate` and `physical_turn` instead of `rotate` and `master_turn`, and assert on `physical_rotate.call_args[0][0]`.
- `test_no_cursor_outside_cursor_pages_or_on_plus` and `test_snapshot_and_render_marks` stay as they are.

- [ ] **Step 2: Write `tests/test_mk3_controller_profiles.py` (failing)**

Fixture: as `CursorTests.setUp` (temporary `Application`, `control_level=2`, `ControllerInputs`, `Mk3Surface`), plus:
- `use(self, ident, *bindings)`: when bindings are given, write `{'format':1,'name':ident,'device':'mk3','bindings':[...]}` to `Path(self.tmp.name)/'controller-profiles'/f'{ident}.json'`; then `self.a.controller_profiles.load()` and set the setting to `ident`.
- `twin(self)`: a second `Application(self.tmp.name)` and `Mk3Surface` with `control_level=2` and the same page fields (`page`, `channel_page`, `shift`) as `self.a`.

Tests:
- `test_original_profile_is_transparent`: with the default profile, for each `(page,inputs)` in `CHANNEL` (channel_page 0) and `SAMPLER` (with `track()['sample']='x.wav'` and one plug-in, as in the cursor tests), and SHIFT up and down, and each event in `[('turn',1),('button','MASTER LEFT'),('button','MASTER RIGHT'),('button','MASTER UP'),('button','MASTER DOWN'),('button','MASTER PUSH'),('knob',4),('button','KNOB 3 TOUCH')]`: apply it through `physical_turn` / press-release through `physical_button` / `physical_rotate(4,1)` on `self`, and through `rotate(0,1)` / `button` / `rotate(4,1)` on a twin. Then assert equal `page`, `channel_page`, `plugin_slot`, `project`, `clock_phase`, `held` and `touched`.
- `test_default_setting_is_original`: `self.a.settings['controllers']['mk3']['profile']=='original'` and `self.s.active_profile() is ORIGINAL`.
- `test_turn_edit_knob1_dispatches_once_and_edits_once`: `use('k1',{'input':'4D TURN','action':'edit.knob1'})`, page `CHANNEL`. Patch `Mk3Surface.dispatch` with `wraps` and `Mk3Surface.rotate` with `wraps`. `physical_turn(1)` → dispatch called once, rotate called once with `(1,1)`, and the project equals a twin after `rotate(1,1)`.
- `test_knob_follow_dispatches_once_and_edits_once`: cursor profile, `physical_rotate(4,1)` → dispatch called once, rotate called once with `(4,1)`, `cursor_cell()==3`.
- `test_none_disables_input_and_swallows_release`: `use('mute',{'input':'4D LEFT','action':'none'})`, page `SAMPLER` with a plug-in; press/release `MASTER LEFT` through `physical_button` → page, slot and `held` unchanged; then `use('original')` and the same press switches the slot, as on a twin.
- `test_push_page_next`: `use('push',{'input':'4D PUSH','action':'page.next'})`, page `CHANNEL` channel_page 0 → after a press, `channel_page==1`.
- `test_not_applicable_falls_back_without_later_bindings`: `use('na',{'input':'4D LEFT','action':'chain.next'},{'input':'4D LEFT','action':'page.next'})`, page `CHANNEL` channel_page 1, SHIFT down. A press gives the same state as a twin's `button('MASTER LEFT',True/False)` with SHIFT down; in particular `channel_page` is not 2.
- `test_press_owner_fixed_at_press_time`: for each change in `('shift','page','profile')` between press and release of `MASTER RIGHT` under the cursor profile on `CHANNEL`: after the release, `'MASTER RIGHT' not in held`, `'NAV RIGHT'` is in neither `self.inputs.buttons` nor `self.a.held_buttons`, and `press_owner` is empty. Also: an original-owned press (SHIFT down) whose release comes with SHIFT up still goes to `button('MASTER RIGHT',False)` (patch with `wraps`; assert it was called with `False`).
- `test_repeat_press_while_owned_runs_once`: cursor profile, `CHANNEL` 0: `physical_button('MASTER RIGHT',True)` twice → `cursor_cell()==2`.
- `test_knob_touch_none_and_follow`: `use('t',{'input':'KNOB TOUCH','action':'none'})` → press/release `KNOB 3 TOUCH` leaves `touched` empty throughout. `use('f',{'input':'KNOB TOUCH','action':'cursor.follow'})` → the press adds to `touched` and sets `cursor_cell()==2` (`CHANNEL` 0); the release removes it from `touched`.
- `test_action_error_consumes_event`: cursor profile; patch `app.mk3_actions.run` to raise `RuntimeError` → `physical_turn(1)` leaves the project unchanged, `a.message=='PROFILE ERROR'`, no exception escapes; the next `physical_turn(1)` with the patch removed edits normally.
- `test_failed_button_action_keeps_profile_ownership`: cursor profile, `CHANNEL` 0, patch `app.mk3_actions.run` to raise; press `MASTER RIGHT` through `physical_button`, then press SHIFT and change `channel_page`, then release `MASTER RIGHT` → `press_owner` empty, `'MASTER RIGHT' not in held`, `button` (patched with `wraps`) never called with `('MASTER RIGHT',False)`, and `'NAV RIGHT'` in neither `self.inputs.buttons` nor `self.a.held_buttons`.
- `test_update_lock_blocks_profile_actions`: cursor profile, `a.update_lock_until=time.monotonic()+60`, `CHANNEL` 0 → `physical_turn(1)` and a `MASTER RIGHT` press change neither the project nor `cursor_cell()`.
- `test_master_mode_overrides_binding`: `use('k1',{'input':'4D TURN','action':'edit.knob1'})`; with `TEMPO` latched (press TEMPO), `physical_turn(2)` equals a twin's `rotate(0,2)` with `TEMPO` latched.
- `test_missing_profile_falls_back_once`: set the setting to `'gone'` → `active_profile() is ORIGINAL`, `a.message=='PROFILE NOT FOUND'`; clear the message, call again → the message stays empty; the setting is still `'gone'`.
- `test_plus_ignores_profiles`: `PlusSurface` with the setting `'cursor'` on `CHANNEL` 0 → `physical_turn(1)` changes `clock_phase` (with `arrange_grid='1/4'`) and not the project.

- [ ] **Step 3: Run the new and adapted tests and confirm they fail**

Run: `/usr/bin/python3 -m unittest tests.test_mk3_controller_profiles tests.test_mk3_parameter_cursor tests.test_mk3_chain_cards`
Expected: failures and errors (`physical_turn`/`physical_button` missing; chain cards fail on left/right slot switching).

- [ ] **Step 4: Settings and store**

In `init_controller_settings` (`app/controller_settings.py`):
- For `device=='mk3'` only, set default `profile='original'`; validate with `type(value) is str`. Add that branch before the generic `else`.
- Create `app.controller_profiles=ProfileStore(Path(app.root)/'controller-profiles')` and call `.load()`.

- [ ] **Step 5: Delivery hooks**

- `Mk2Surface` gets the two pass-through methods.
- `Mk2Session.read` line 119: call `self.surface.physical_button(...)`.
- `rotate_raw` (lines 140 and 157): call `self.surface.physical_rotate(...)`.
- `Mk3Session.rotate_raw`: for index 0, call `self.surface.physical_turn(delta)`; otherwise `super()`.

- [ ] **Step 6: `app/mk3_actions.py`**

- Move `cursor_active`, `cursor_key`, `populated`, `cursor_cell` and `move_cursor` from `Mk3Surface` into `class CursorState` without changing their bodies. The `cursors` dict is initialised by `Mk3Surface.__init__`.
- `run(surface, action, index, delta)`:
  - `cursor.edit`: cell = `cursor_cell()`; `None` → False; else `surface.rotate(cell+1, delta)`, True.
  - `edit.knobN`: `fields()[N-1] is None` → False; else `surface.rotate(N, delta)`, True.
  - `transport.move`: `rotate(0, delta)`, True.
  - `transport.back` / `transport.forward`: `rotate(0, -1)` / `rotate(0, 1)`, True.
  - `cursor.previous` / `cursor.next`: `move_cursor(-1 / 1)`, True.
  - `page.previous` / `page.next`: `change_page(-1 / 1)`, True.
  - `chain.previous` / `chain.next`: `return surface.switch_chain(-1 / 1)`.
  - `cursor.follow`: if `fields()[index-1]` is not `None`, set `cursors[cursor_key()] = index-1`; return False, so the original handling continues.

- [ ] **Step 7: `Mk3Surface`**

- Inherit `CursorState`.
- In `__init__`, replace `cursor_buttons` with `self.press_owner={}`.
- Remove the cursor interception from `button` and from `rotate`, which restores the `cebddb3` bodies (`git show cebddb3:app/mk3_surface.py`). Remove `master_turn`.
- Extract the chain-slot block in `button` into `switch_chain(step)`. It returns False off `SAMPLER`/`PLUGIN`/`AUDIO LOOP`. Otherwise it applies the existing clamped switch and returns True, even when already at the end, as the original does. Have the original block call it with `-1` for LEFT/UP and `1` for RIGHT/DOWN.
- In `disconnect`, clear `press_owner`.
- Dispatch:

```python
INTERCEPTED={'MASTER UP':'4D UP','MASTER DOWN':'4D DOWN','MASTER LEFT':'4D LEFT','MASTER RIGHT':'4D RIGHT','MASTER PUSH':'4D PUSH',
             **{f'KNOB {n} TOUCH':'KNOB TOUCH' for n in range(1,9)}}

def dispatch(self,input,index,delta):
    a=self.app
    if self.source!='mk3' or not self.cursor_active() or time.monotonic()<getattr(a,'update_lock_until',0):return 'original'
    profile=self.active_profile()
    binding=profile.match(input,a.page,a.shift,self.cursor_cell() is not None)
    if binding is None or binding.action=='default':return 'original'
    if binding.action=='none':return 'profile'
    try:acted=mk3_actions.run(self,binding.action,index,delta)
    except Exception as error:
        print(f'controller profile {profile.ident} binding {binding.index} {input}: {error!r}',flush=True)
        a.message='PROFILE ERROR';return 'profile'
    return 'profile' if acted else 'original'

def physical_button(self,name,pressed):
    if name not in INTERCEPTED:return self.button(name,pressed)
    if not pressed:
        if self.press_owner.pop(name,'original')=='profile':self.held.discard(name);return
        return self.button(name,False)
    owner=self.press_owner.get(name)
    if owner is None:
        index=int(name.split()[1]) if name.startswith('KNOB') else None
        owner=self.press_owner[name]=self.dispatch(INTERCEPTED[name],index,0)
        if owner=='profile':self.held.add(name)
    if owner=='original':return self.button(name,True)
```

  `physical_turn(delta)`: `if self.dispatch('4D TURN',None,delta)=='original':self.rotate(0,delta)`.

  `physical_rotate(index,delta)`: index 0 → `physical_turn`; else `if self.dispatch('KNOB TURN',index,delta)=='original':self.rotate(index,delta)`.

  `active_profile()`: look up the setting in `app.controller_profiles`. When it is missing, set `a.message='PROFILE NOT FOUND'` only if `self.missing_profile != ident`, then remember `ident` and return `ORIGINAL`. Reset `self.missing_profile=None` whenever a lookup succeeds.

- `mk3_actions` is imported as a module (`from app import mk3_actions`) so the error test can patch `mk3_actions.run`.
- Leave `Mk3Session.update`'s `state['cursor']` as it is; Task 3 changes it.

- [ ] **Step 8: Run the focused tests**

Run: `/usr/bin/python3 -m unittest tests.test_controller_profiles tests.test_mk3_controller_profiles tests.test_mk3_parameter_cursor tests.test_mk3_chain_cards -v`
Expected: all OK.

- [ ] **Step 9: Prove the pre-cursor MK3 tests pass unchanged**

```bash
git diff --exit-code cebddb3 -- $(git ls-tree --name-only cebddb3 tests/ | grep '^tests/test_mk3_')
/usr/bin/python3 -m unittest $(git ls-tree --name-only cebddb3 tests/ | grep '^tests/test_mk3_' | sed 's#/#.#;s#\.py$##')
```
Expected: the diff is empty (exit 0), and all tests pass.

- [ ] **Step 10: Commit**

```bash
git add app/mk3_actions.py app/mk3_surface.py app/mk2_surface.py app/mk2_session.py app/mk3_session.py app/controller_settings.py tests/test_mk3_chain_cards.py tests/test_mk3_parameter_cursor.py tests/test_mk3_controller_profiles.py
git commit -m "Dispatch MK3 navigation through controller profiles"
```

---

### Task 3: Profile selection page and cursor indicator

**Files:**
- Modify: `app/settings_menu.py` (WORKFLOW entry, `SETTING_PAGES`, reload on open)
- Modify: `app/mk2_surface.py` (`CONTROLLER PROFILE` field and its rotate branch)
- Modify: `app/mk2_encoders.py:26` (`'profile'` is a discrete controller key)
- Modify: `app/model.py` (`CONTROLLER PROFILE` body text, next to `COLOR SCHEME`)
- Modify: `app/mk3_surface.py` (`indicator_cell()`)
- Modify: `app/mk3_session.py` (`state['cursor']=self.surface.indicator_cell()`)
- Test: `tests/test_mk3_controller_profiles.py` (append)

**Interfaces:**
- Consumes (Task 2): `active_profile()`, `cursor_cell()`, `app.controller_profiles`, the `profile` setting.
- Produces: `Mk3Surface.indicator_cell(self) -> int|None`; page name `'CONTROLLER PROFILE'`.

- [ ] **Step 1: Append failing tests**

- `test_profile_page_only_on_mk3_workflow`:
  - Set `settings_section='WORKFLOW'`.
  - Under `controller_context(a,'mk3')`, `'CONTROLLER PROFILE' in a.setting_entries()` is true.
  - Under `plus`, `mk2` and `mikro` it is false.
- `test_profile_page_cycles_saves_and_applies`:
  - Write a user profile `zz.json`. Under the mk3 context, select the entry and call `a.open_setting()`, so `a.page=='CONTROLLER PROFILE'`.
  - `fields()[0]` has label `PROFILE` and value `Original`.
  - `rotate(1,1)`: the value becomes `4D cursor`, the setting is `'cursor'`, and the saved settings file holds the same value (read `a.settings_path`).
  - `rotate(1,1)` again: the setting is `'zz'`. `rotate(1,10)` stays on `'zz'` (clamped). `rotate(1,-10)` gives `'original'`.
- `test_open_page_reloads_files`:
  - Open the page, then write `new.json`.
  - Leave and re-open the page with `settings_back()` and `open_setting()`; `'new'` is now in `a.controller_profiles.ids()`.
- `test_invalid_selected_profile_falls_back_and_recovers`:
  - Select a valid `mine` profile containing `4D TURN → edit.knob1`, then overwrite the file with `'{'` and re-open the page.
  - `active_profile() is ORIGINAL` and `a.message=='PROFILE NOT FOUND'`.
  - Restore a valid file and re-open the page: `active_profile().ident=='mine'`.
- `test_indicator_follows_applicable_cursor_bindings`, on `CHANNEL`, channel_page 0:
  - Original: `indicator_cell()` is `None`.
  - Cursor profile: it is `0`.
  - Cursor profile with SHIFT held: still `0`.
  - Profile `{'input':'4D TURN','action':'cursor.edit','pages':'MACRO'}`: `None` on `CHANNEL`, an int on `MACRO`.
  - Cursor profile with `TEMPO` latched: `None`.
- `test_session_snapshot_uses_indicator`:
  - With Original selected, `Mk3Session.update` (set up as in `test_snapshot_and_render_marks`) submits `cursor` as `None`.
  - With the cursor profile it submits the cell.

- [ ] **Step 2: Run them and confirm they fail**

Run: `/usr/bin/python3 -m unittest tests.test_mk3_controller_profiles -v`
Expected: the new tests fail; the Task 2 tests still pass.

- [ ] **Step 3: Implement**

- **Settings menu:**
  - `setting_entries`: when `self.settings_section=='WORKFLOW' and self.controller_source=='mk3'`, append `'CONTROLLER PROFILE'`.
  - Add `'CONTROLLER PROFILE'` to `SETTING_PAGES`.
  - `open_setting`: when `selected=='CONTROLLER PROFILE'`, call `self.controller_profiles.load()` before setting the page.
- **`Mk2Surface.fields`:**
  - Next to `COLOR SCHEME`: when `a.page=='CONTROLLER PROFILE' and self.source=='mk3'`, show `field(0,'PROFILE',<active profile name>,_controller_key='profile')` and return.
  - The name comes from `self.active_profile().name` when the surface has it, else `'Original'`.
- **Rotate branch for `key=='profile'`:**
  - `ids=a.controller_profiles.ids()`. Start from the current position, or 0 if the setting is not in `ids`.
  - Clamp to `[0,len(ids)-1]`, save the new id into the setting and call `save_json(a.settings_path,a.settings)`.
- **Other changes:**
  - `mk2_encoders.py:26`: add `'profile'` to the discrete tuple.
  - `model.py` body for the page: `[name, 'MK3 4D AND KNOBS', 'ID '+ident]`, footer `'ENTER BACK'`.
  - `indicator_cell()`: `cell=self.cursor_cell()`; return `cell` if `cell is not None and self.active_profile().shows_cursor(self.app.page)`, else `None`.
  - Session: `state['cursor']=self.surface.indicator_cell()`.

- [ ] **Step 4: Run the focused and MK3 tests**

Run: `/usr/bin/python3 -m unittest tests.test_controller_profiles tests.test_mk3_controller_profiles tests.test_mk3_parameter_cursor tests.test_mk3_chain_cards tests.test_mk3_themes`
Expected: all OK.

- [ ] **Step 5: Commit**

```bash
git add app/settings_menu.py app/mk2_surface.py app/mk2_encoders.py app/model.py app/mk3_surface.py app/mk3_session.py tests/test_mk3_controller_profiles.py
git commit -m "Add MK3 controller profile setting and profile-aware cursor indicator"
```

---

### Task 4: Documentation and full verification

**Files:**
- Create: `docs/CONTROLLER_PROFILES.md`
- Modify: `docs/MK3_SUPPORT.md` (the 4D cursor paragraph, lines 5–7)
- Test: `tests/test_controller_profiles.py` (append one docs test)

**Interfaces:**
- Consumes: `INPUTS`, `ACTIONS`, `GROUPS`, `validate` (Task 1).

- [ ] **Step 1: Append a failing docs test**

`test_documented_examples_validate_and_document_every_name`:
- Read `docs/CONTROLLER_PROFILES.md`.
- Every fenced ```json block in it parses and passes `validate('doc', ...)`.
- Every input, every action across `ACTIONS` and every group name appears in the text in backticks.

- [ ] **Step 2: Write `docs/CONTROLLER_PROFILES.md`**

Sections, in this order:
- **What profiles are:** data only, never executed; MK3 only; the inputs covered.
- **Choosing one:** SETTINGS › SYSTEM › WORKFLOW › CONTROLLER PROFILE; the default is Original.
- **Where user files go:** `<data folder>/controller-profiles/<id>.json`, e.g. `~/Music/maschinista/controller-profiles/`; the identifier rule; re-opening the page reloads the files.
- **File format:** a table of top-level keys and binding keys with their limits.
- **Inputs and actions:** the table from the spec; every action with a one-line meaning; "not applicable" falls back to the original handling and does not try later bindings.
- **Matching:**
  - The first binding that matches wins.
  - Master modes always take priority.
  - Profiles apply only on the parameter pages.
  - Press and release ownership.
- **Errors:** where to see them (`journalctl --user -u machinista`), `PROFILE NOT FOUND`, `PROFILE ERROR`.
- **Compatibility promise for format 1:** copied from the spec.
- **Examples,** each a complete ```json block:
  - the built-in 4D cursor profile;
  - "4D turn edits knob 1";
  - "4D push goes to the next page".

- [ ] **Step 3: Update `docs/MK3_SUPPORT.md`**

- Describe the 4D cursor as the `4D cursor` profile, chosen under SETTINGS › SYSTEM › WORKFLOW › CONTROLLER PROFILE.
- Say that under Original (the default) the 4D encoder behaves as before.
- Link `CONTROLLER_PROFILES.md`.
- Keep the existing cursor description, framed as what the profile does.

- [ ] **Step 4: Run the docs test, then the full suite**

Run: `/usr/bin/python3 -m unittest tests.test_controller_profiles -v`, then `/usr/bin/python3 -m unittest discover -s tests 2>&1 | grep -E '^(FAIL|ERROR):|^Ran|^FAILED|^OK'`
Expected: the docs test passes. The full suite shows only the 7 known LV2 fixture failures from Global Constraints, if `build/audio_engine` exists; without a native build those tests are skipped.

- [ ] **Step 5: Commit**

```bash
git add docs/CONTROLLER_PROFILES.md docs/MK3_SUPPORT.md tests/test_controller_profiles.py
git commit -m "Document MK3 controller profiles"
```
