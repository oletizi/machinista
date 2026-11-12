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
- `name`: non-empty string, at most 24 characters (fits the settings cell);
  unique across loaded profiles, case-insensitive. The built-in names win a
  clash; a user file with a clashing name is rejected.
- `device`: must be `"mk3"`.
- `bindings`: list, at most 64 entries. May be empty.
- `note`: optional string, ignored.

Binding keys:

- `input` (required): one of the inputs below.
- `action` (required): one of the actions valid for that input.
- `pages` (optional): a page name, a list of page names, or a group name.
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

"Not applicable" means the action falls through to the original handling for
that input, the same as `default`.

## Matching and dispatch

For an input event, Machinista picks the first binding (file order) whose
`input` matches and whose `pages`, `shift` and `cursor` conditions all hold,
and runs its action. No match → original handling. Held VOLUME / SWING / TEMPO
master modes always take precedence: while one is held, profiles are not
consulted. Profiles are also not consulted on pages outside `parameters`.

Press handling keeps the current rules: an action runs once per press (the
existing `held` guard; no auto-repeat), and a release is routed to the handler
that took its press — a profile action's release is swallowed even if SHIFT
or the page changed in between (generalising the existing `cursor_buttons`
fix). A `KNOB TOUCH` release always takes the original handling.

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

**Cursor indicator:** the bar below the cursor cell is drawn only when the
active profile has at least one `cursor.*` binding. Cursor memory (per view,
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
  then valid user profiles sorted by name; the change applies immediately and
  is saved as `settings['controllers']['mk3']['profile']` (the profile name).
  Default: `"Original"`.
- If the saved name is not among the loaded profiles, the controller uses
  Original and shows `PROFILE NOT FOUND` once; the saved name is kept, so the
  profile comes back when its file is fixed.

## Components

- `app/controller_profiles.py`: constants (inputs, actions per input, page
  groups, limits), `validate(data) -> Profile` raising `ProfileError(reason)`,
  `load_profiles(root) -> list[Profile]` (built-ins first, then users;
  rejections logged), `Profile.match(input, page, shift, cursor) -> str|None`.
  No MK3 or surface imports.
- `app/controller_profiles/cursor.json`: the 4D cursor built-in.
- `app/mk3_actions.py`: `run(surface, action, input, index, delta) -> bool`
  (False = not applicable); the cursor state and logic moved out of
  `mk3_surface.py`, and the chain-slot switch extracted into a function shared
  by the original handler and `chain.*`.
- `app/mk3_surface.py`: dispatch at the four entry points (`master_turn`,
  `button` for `MASTER UP/DOWN/LEFT/RIGHT/PUSH` and `KNOB n TOUCH`, `rotate`
  1–8); the cursor-specific code there is replaced by the dispatch.
- `app/controller_settings.py`: default `profile='Original'` for `mk3`, type
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
name this Machinista does not know, or a higher `format`, is rejected whole
with "needs a newer Machinista" in the journal. `Original` always means the
current upstream behaviour.

## Error handling

Validation is the only defence needed: actions are Machinista code, so a
loaded profile cannot raise in an unexpected way beyond what the original
handlers can. Unreadable, invalid or oversized files are skipped with a reason;
a missing selected profile falls back to Original. Profiles are UI behaviour
only; they are never written into projects.

## Testing

- `tests/test_controller_profiles.py`: valid minimal file; each rejection
  (bad JSON, `format` 2, wrong device, unknown key, unknown input, unknown
  action, action not valid for input, bad page, bad group, wrong types, too
  many bindings, long or duplicate name, oversized file, symlink); first-match
  order; each condition; every built-in validates.
- `tests/test_mk3_parameter_cursor.py` runs with the 4D cursor profile selected
  and passes with only fixture changes.
- The existing MK3 tests (`tests/test_mk3_*.py`, chain cards with its original
  left/right slot switching restored) pass with Original selected, the default.
- `tests/test_mk3_controller_profiles.py`: switching profiles on the settings
  page applies immediately and persists; missing profile falls back to
  Original; a custom profile with `4D TURN → edit.knob1`, one with
  `4D LEFT → none`, one with `4D PUSH → page.next`; `chain.*` off a chain page
  falls through; profile release routing with SHIFT released first; no cursor
  bar under Original; master modes override bindings; Maschine+ ignores
  profiles.
- Full suite compared with the known baseline (7 LV2 fixture failures). Final
  acceptance: switching between Original and 4D cursor on the MK3.
