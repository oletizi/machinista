# MK3 controller profiles — design

Date: 2026-11-11 · Branch: `mk3-controller-profiles` (from `mk3-4d-parameter-cursor`)

## Goal

Make the MK3's navigation behaviour selectable, so a user can switch between the
original controller behaviour and the 4D-encoder parameter cursor, and can
define their own behaviour without changing Machinista's code.

Behaviours are **data, never code**. A profile is a JSON file that binds inputs
to actions from a fixed list implemented in Machinista. Loading a profile never
executes anything from the file; the worst a bad or hostile file can do is
bind controls badly, and invalid files are rejected whole. A new kind of
behaviour that the action list cannot express is a code change to Machinista,
which then adds the action to the list.

## Scope

- MK3 only (`Mk3Surface.source == 'mk3'`). The Maschine+ (`PlusSurface`) and
  other controllers keep their current behaviour and ignore profiles.
- Inputs: the 4D encoder (turn, push, up, down, left, right) and the eight
  knobs (turn, touch). All other buttons, pads and the touch strip are out of
  scope.
- No web UI control in this round; profiles are chosen on the device.

## Profile file

```json
{
  "format": 1,
  "name": "4D cursor",
  "device": "mk3",
  "bindings": [
    {"input": "4D TURN", "pages": "parameters", "shift": false, "cursor": true,
     "action": "cursor.edit", "note": "one click = one step"}
  ]
}
```

Top-level keys, all required except where noted:

- `format`: integer, must be `1`. A higher value is rejected with
  "needs a newer Machinista".
- `name`: non-empty string, at most 24 characters (fits the settings cell).
  Display only; it need not be unique.
- `device`: must be `"mk3"`.
- `bindings`: list, at most 64 entries. May be empty.
- `note`: optional string, ignored.

Binding keys:

- `input` (required): one of the inputs below.
- `action` (required): one of the actions valid for that input.
- `pages` (optional): a page name, a group name, or a list mixing page and
  group names (expanded and combined).
  Groups: `parameters` = `PAD`, `CHANNEL`, `SAMPLER`, `PLUGIN`, `INPUT`,
  `GROOVE`, `MACRO`, `AUDIO LOOP` (`CONTROL_PAGES` plus `AUDIO LOOP`);
  `chain` = `SAMPLER`, `PLUGIN`, `AUDIO LOOP`. Page names must be one of the
  `parameters` pages; other pages always keep the original behaviour.
  Omitted = any `parameters` page.
- `shift` (optional): `true` or `false`; omitted = either.
- `cursor` (optional): `true` when the current view has at least one non-empty
  parameter cell, `false` when it has none; omitted = either.
- `note` (optional): string, ignored.

Any other key, an unknown input, action, page or group, an action not valid for
its input, or a wrong type rejects the whole file. The reason (file, binding
index, key) goes to the journal. A rejected file is never partly applied.
Unknown names are reported as, e.g., `unknown action 'cursor.nxt' (misspelt,
or added in a newer Machinista)`; only `format` above 1 is reported as
definitely needing a newer Machinista.

**Identity.** A profile's identifier is its file name without `.json`
(built-ins: `original`, `cursor`). It must match `[a-z0-9][a-z0-9-]{0,31}`;
other file names are skipped with a journal message. A user file whose
identifier equals a built-in's is rejected. The identifier, not the display
name, is what the selection stores, so editing `name` keeps the selection;
renaming the file makes it a different profile (format-1 contract).

## Inputs and actions

| Input | Event | Valid actions |
|---|---|---|
| `4D TURN` | turn, `delta` steps | `cursor.edit`, `edit.knob1`…`edit.knob8`, `transport.move` |
| `4D UP`, `4D DOWN`, `4D LEFT`, `4D RIGHT`, `4D PUSH` | press | `cursor.previous`, `cursor.next`, `page.previous`, `page.next`, `chain.previous`, `chain.next`, `transport.back`, `transport.forward` |
| `KNOB TURN` | knob *n* turned | `cursor.follow` |
| `KNOB TOUCH` | knob *n* touched | `cursor.follow` |
| any | | `default`, `none` |

Physical names: `4D TURN` is the session's index-0 rotation
(`Mk3Session.rotate_raw(0)`); `4D UP/DOWN/LEFT/RIGHT/PUSH` are `MASTER UP`,
`MASTER DOWN`, `MASTER LEFT`, `MASTER RIGHT`, `MASTER PUSH`; `KNOB TURN` is
`rotate(1…8)`; `KNOB TOUCH` is the `KNOB n TOUCH` press.

Actions:

- `default`: the original handling for this input, as if no binding matched.
- `none`: the input does nothing (a release is also swallowed).
- `cursor.edit`: apply `delta` steps to the cursor cell's parameter, through
  `rotate(cell + 1, delta)` (same steps, clamping, undo, automation and
  feedback as a knob). Not applicable when the view has no cursor cell.
- `cursor.previous` / `cursor.next`: move the cursor to the previous / next
  non-empty cell; past either end, run the bounded page traversal defined in
  the 4D-cursor spec (`2026-11-11-mk3-4d-parameter-cursor-design.md`), with no
  rollback.
- `cursor.follow`: if knob *n*'s cell is non-empty, set the cursor to it; then
  continue with the original handling (the knob still turns or highlights).
- `edit.knob1`…`edit.knob8`: apply `delta` steps to that cell, through
  `rotate(n, delta)`. Not applicable when that cell is empty.
- `page.previous` / `page.next`: `change_page(-1 / +1)`, as PAGE LEFT/RIGHT.
- `chain.previous` / `chain.next`: switch to the previous / next chain slot,
  the existing MK3 handler for `SAMPLER` / `PLUGIN` / `AUDIO LOOP`. Not
  applicable on other pages.
- `transport.move`: `rotate(0, delta)` with no profile involvement — the
  original 4D-turn handling on the current page.
- `transport.back` / `transport.forward`: `rotate(0, -1 / +1)`, as the
  original MASTER UP/DOWN on non-chain parameter pages.

"Not applicable" means the input gets the original handling, the same as
`default`. Later bindings are **not** tried: matching picks one binding, and
that binding's outcome is final.

## Original handling

"Original handling" is the MK3 surface's own, profile-free code path:
`Mk3Surface.button()` and `Mk3Surface.rotate()` with the cursor code removed
from them. Concretely, it is the behaviour of `mk3-linux-desktop` before the
cursor branch (`cebddb3`), plus any later upstream changes to that path. The
cursor branch's interceptions in `button()` (MASTER LEFT/RIGHT, the
`cursor_buttons` set), `rotate()` (cursor recording) and `master_turn()` are
removed; their logic exists only in `app/mk3_actions.py`, reachable only from
profile actions. So Original is "no bindings" over a path that contains no
cursor logic, and it tracks upstream's MK3 behaviour as it evolves.

## Dispatch boundary

Profile matching happens exactly once per physical event, at the boundary
where the session delivers it to the surface:

- `Mk2Session` delivers button events through `surface.physical_button(name,
  pressed)` and quantised knob steps (indices 1–8) through
  `surface.physical_rotate(index, steps)` (today: `surface.button` at
  `app/mk2_session.py:119`, `surface.rotate` at `:157`). The base surface
  implements both as plain calls to `button` / `rotate`, so other controllers
  are unchanged.
- `Mk3Session.rotate_raw(0, delta)` calls `surface.physical_turn(delta)`
  (replacing `master_turn`).
- `Mk3Surface` overrides the three `physical_*` methods to consult the
  profile. `button()` and `rotate()` never consult it.

Actions call only the non-dispatching operations: `cursor.edit` and
`edit.knobN` call `rotate(n, delta)`, `transport.*` call `rotate(0, ±n)`,
`cursor.follow` sets the cursor and then calls `rotate(n, steps)` or
`button('KNOB n TOUCH', True)`. A physical event therefore produces one
dispatch and at most one edit, with the existing undo, automation, clamping and
display semantics. Synthetic callers (MASTER UP/DOWN calling `rotate(0, ±1)`,
`super().button(...)` remaps inside the surface) never reach a profile.

## Matching

For an input event, Machinista picks the first binding (file order) whose
`input` matches and whose `pages`, `shift` and `cursor` conditions all hold,
and runs its action. No match → original handling. Held VOLUME / SWING / TEMPO
master modes always take precedence: while one is held, profiles are not
consulted. Profiles are also not consulted on pages outside `parameters`.

## Press ownership

Every intercepted button (`MASTER UP/DOWN/LEFT/RIGHT/PUSH`, `KNOB n TOUCH`)
gets an owner when it is pressed, recorded in `surface.press_owner[name]`:

- `profile` once a matching binding with an action other than `default` is
  chosen and that action does not report "not applicable" (including `none`,
  and including an action that raises: the owner is `profile` whether the
  action completes or fails), and
- `original` when there was no match, the action was `default`, it was not
  applicable, or profiles were not consulted (master mode, other page,
  Maschine+), or the action was `cursor.follow` (which continues into the
  original handling).

A release goes to its press's owner and then clears the entry: `original` →
`button(name, False)`, exactly as today (so `held`, `touched` and other release
effects are preserved); `profile` → the release is consumed and `name` is
removed from `held`. A release with no recorded owner (e.g. the press happened
before a reconnect) takes the original handling. Ownership is decided at press
time only, so SHIFT, page, profile or file changes between press and release
do not move it. A profile action runs once per press (no auto-repeat); a second
press report while owned is ignored. Disconnect clears all owners.

`KNOB n TOUCH` follows the same rule: with `cursor.follow` the press is owned
by `original` (the touch highlight shows and clears normally); with `none` the
press and its release are both consumed.

**Original profile:** built-in, `bindings: []`. It is therefore exactly the
original behaviour, now and after future upstream changes to it.

**4D cursor profile:** built-in, shipped as `app/controller_profiles/cursor.json`
and loaded by the same validator as user files. It reproduces the behaviour of
`mk3-4d-parameter-cursor`:

```json
[
  {"input": "4D TURN",  "shift": false, "cursor": true, "action": "cursor.edit"},
  {"input": "4D LEFT",  "shift": false, "cursor": true, "action": "cursor.previous"},
  {"input": "4D RIGHT", "shift": false, "cursor": true, "action": "cursor.next"},
  {"input": "4D LEFT",  "pages": ["PAD","CHANNEL","INPUT","GROOVE","MACRO"], "shift": false, "action": "cursor.previous"},
  {"input": "4D RIGHT", "pages": ["PAD","CHANNEL","INPUT","GROOVE","MACRO"], "shift": false, "action": "cursor.next"},
  {"input": "KNOB TURN", "action": "cursor.follow"}
]
```

**Cursor indicator:** the bar below the cursor cell is drawn when the current
view has a cursor cell and the active profile has a binding with a `cursor.*`
action whose `pages` and `cursor` conditions hold in the current view. `shift`
is ignored for this test, so holding SHIFT does not make the bar flicker. No
master mode may be held. So the bar appears exactly where a cursor action can
apply. Cursor memory (per view,
per plug-in layout) stays on the surface and survives profile switches.

## Loading and selection

- Built-ins load from `app/controller_profiles/*.json` (Original is defined in
  code as the empty profile). A built-in that fails validation is a bug: tests
  load every built-in.
- User profiles load from `<data root>/controller-profiles/*.json`
  (`paths.data`, e.g. `~/Music/maschinista/controller-profiles/`). Files over
  64 KiB, symlinks and non-regular files are skipped with a journal message.
  The web file manager accepts only `.wav`/`.mp3`, so it cannot write here.
- Profiles are read at start-up and again whenever the PROFILE settings page
  is opened, so an edited file is picked up without a restart.
- Selection: SETTINGS › SYSTEM › WORKFLOW › CONTROLLER PROFILE (MK3 only,
  added like COLOR SCHEME under DISPLAY). Turning cycles Original, 4D cursor,
  then valid user profiles sorted by identifier; the change applies
  immediately and is saved as `settings['controllers']['mk3']['profile']` (the
  identifier). Default: `"original"`.
- If the saved identifier is not among the loaded profiles, the controller
  uses Original and shows `PROFILE NOT FOUND` once; the saved identifier is
  kept, so the profile comes back when its file is fixed.
- Loading never raises: any error reading or validating a user file (I/O,
  JSON, encoding, validation) skips that file with a journal message. Start-up
  and opening the settings page cannot fail because of user files.

## Components

- `app/controller_profiles.py`: constants (inputs, actions per input, page
  groups, limits), `validate(ident, data) -> Profile` raising
  `ProfileError(reason)`, `load_profiles(root) -> list[Profile]` (built-ins
  first, then users; rejections logged, never raises),
  `Profile.match(input, page, shift, cursor) -> Binding|None`,
  `Profile.shows_cursor(page, cursor) -> bool`. No MK3 or surface imports.
- `app/controller_profiles/cursor.json`: the 4D cursor built-in.
- `app/mk3_actions.py`: `run(surface, action, input, index, delta) -> bool`
  (False = not applicable); the cursor state and logic moved out of
  `mk3_surface.py`, and the chain-slot switch extracted into a function shared
  by the original handler and `chain.*`.
- `app/mk2_session.py`, `app/surface.py` or `app/mk2_surface.py`: the
  `physical_button` / `physical_rotate` delivery hooks (plain pass-through by
  default).
- `app/mk3_surface.py`: `physical_turn`, `physical_button`, `physical_rotate`
  (dispatch and press ownership); the cursor code removed from `button`,
  `rotate` and `master_turn`.
- `app/controller_settings.py`: default `profile='original'` for `mk3`, type
  check (string).
- `app/settings_menu.py`, `app/mk2_surface.py`: the CONTROLLER PROFILE page
  and its field.
- `app/mk3_session.py`: `state['cursor']` only when the profile shows the
  indicator.
- `docs/CONTROLLER_PROFILES.md`: the contract — every input, condition and
  action, the compatibility promise, the file location, both built-ins as
  worked examples, and a "4D edits knob 1" example.
- `docs/MK3_SUPPORT.md`: the 4D cursor described as a profile; how to choose it.

## Compatibility promise

Within `format: 1`: an existing input, condition, group or action name never
changes meaning and is never removed; new ones may be added. A file using a
name this Machinista does not know is rejected whole, reported as "misspelt, or
added in a newer Machinista"; a file with a higher `format` is rejected whole,
reported as needing a newer Machinista. `Original` always means the
current upstream behaviour.

## Error handling

Validation keeps unknown data out; it does not make actions infallible. At the
action boundary:

- Each action checks its own preconditions (cursor cell exists, knob cell
  non-empty, chain page) and reports "not applicable" rather than acting on a
  missing target; that falls back to the original handling as above.
- If an action raises anyway, the exception goes to the journal with the
  profile, binding index and input, the display shows `PROFILE ERROR`, and
  the event is consumed (owner `profile`). It does not fall back to the
  original handling, because a half-applied action followed by the original
  one could apply two edits. The controller keeps running; the profile stays
  selected.

Unreadable, invalid or oversized files are skipped with a reason; a missing
selected profile falls back to Original. Profiles are UI behaviour only; they
are never written into projects.

## Testing

- `tests/test_controller_profiles.py`: valid minimal file; each rejection
  (bad JSON, `format` 2, wrong device, unknown key, unknown input, unknown
  action, action not valid for input, bad page, bad group, wrong types, too
  many bindings, long name, bad file name, built-in identifier clash,
  oversized file, symlink); a loader run over a folder with good and bad files
  returns the good ones and does not raise; first-match order with an
  overlapping broad rule before a specific one and the reverse; omitted
  conditions; group expansion; a `pages` list mixing names and groups; each
  condition; `shows_cursor`; every built-in validates.
- `tests/test_mk3_parameter_cursor.py` runs with the 4D cursor profile selected
  and passes with only fixture changes.
- Original is checked against the pre-cursor behaviour, not against the new
  dispatcher: every `tests/test_mk3_*.py` file as it is at `cebddb3` (before
  the cursor branch) passes unchanged with Original selected, the default.
- `tests/test_mk3_controller_profiles.py`: switching profiles on the settings
  page applies immediately and persists; missing profile falls back to
  Original; a custom profile with `4D TURN → edit.knob1`, one with
  `4D LEFT → none`, one with `4D PUSH → page.next`; `4D TURN → edit.knob1` and
  `KNOB TURN → cursor.follow` each produce exactly one edit and one dispatch;
  a not-applicable action (`chain.next` off a chain page) gets the original
  handling and a later matching binding is not run; press ownership for each
  intercepted button with SHIFT, page and profile changed between press and
  release, and for `default`, `none` and not-applicable outcomes;
  `KNOB TOUCH → none` consumes press and release; an action that raises
  consumes the event and shows `PROFILE ERROR`; cursor bar shown only where a
  cursor binding applies (page-limited binding, SHIFT held, Original); master
  modes override bindings; Maschine+ ignores profiles.
- Full suite compared with the known baseline (7 LV2 fixture failures). Final
  acceptance: switching between Original and 4D cursor on the MK3.
