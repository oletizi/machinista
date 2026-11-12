# Controller profiles

## What profiles are

A profile is a small JSON file that says what the MK3's 4D encoder and knobs do. It is data only. Machinista reads and checks it, and never runs anything from it. A bad file can only be rejected or bind controls badly.

Profiles work on the Maschine MK3 only. Other controllers ignore them.

Inputs covered: the 4D encoder (turn, push, up, down, left, right) and the eight knobs (turn, touch). Every other button, pad and the touch strip keeps its normal behaviour.

## Choosing one

Go to SETTINGS › SYSTEM › WORKFLOW › CONTROLLER PROFILE and turn encoder 1 or the 4D encoder. The change applies at once and is saved. The default is Original, the normal MK3 behaviour. `4D cursor` is built in. Your own valid profiles follow, sorted by file name.

## Where user files go

Put files in `<data folder>/controller-profiles/<id>.json`, for example `~/Music/maschinista/controller-profiles/`. Create the folder if it does not exist.

The identifier `<id>` is the file name without `.json`. It must match `[a-z0-9][a-z0-9-]{0,31}`: lower-case letters, digits and hyphens, starting with a letter or digit, at most 32 characters. Other file names are skipped. `original` and `cursor` are taken by the built-in profiles.

The identifier is what Machinista saves as your choice. Changing `name` keeps your choice. Renaming the file makes it a different profile.

Files are read at start-up and again each time you open the CONTROLLER PROFILE page, so you can edit a file and reopen the page without restarting. Files larger than 65536 bytes, symlinks and anything that is not a plain file are skipped.

## File format

Top-level keys:

| Key | Required | Meaning |
|---|---|---|
| `format` | yes | The number `1`. A higher number is rejected as needing a newer Machinista. |
| `name` | yes | Text, 1 to 24 characters. Shown on the settings page. |
| `device` | yes | The text `"mk3"`. |
| `bindings` | yes | A list of at most 64 bindings. It may be empty. |
| `note` | no | Text for you. Ignored. |

Binding keys:

| Key | Required | Meaning |
|---|---|---|
| `input` | yes | One of the inputs below. |
| `action` | yes | One of the actions valid for that input. |
| `pages` | no | A page name, a group name, or a list mixing both. Left out means any parameter page. |
| `shift` | no | `true` = only while SHIFT is held, `false` = only while it is not. Left out means either. |
| `cursor` | no | `true` = only when the current view has a parameter cell to point at, `false` = only when it has none. Left out means either. |
| `note` | no | Text for you. Ignored. |

Any other key, an unknown name or a wrong type rejects the whole file. A rejected file is never partly applied. The reason is written to the journal.

Pages are the parameter pages: `PAD`, `CHANNEL`, `SAMPLER`, `PLUGIN`, `INPUT`, `GROOVE`, `MACRO` and `AUDIO LOOP`. Two groups save typing:

| Group | Pages |
|---|---|
| `parameters` | `PAD`, `CHANNEL`, `SAMPLER`, `PLUGIN`, `INPUT`, `GROOVE`, `MACRO`, `AUDIO LOOP` |
| `chain` | `SAMPLER`, `PLUGIN`, `AUDIO LOOP` |

## Inputs and actions

| Input | When | Valid actions |
|---|---|---|
| `4D TURN` | The 4D encoder is turned | `cursor.edit`, `edit.knob1`, `edit.knob2`, `edit.knob3`, `edit.knob4`, `edit.knob5`, `edit.knob6`, `edit.knob7`, `edit.knob8`, `transport.move` |
| `4D UP`, `4D DOWN`, `4D LEFT`, `4D RIGHT`, `4D PUSH` | The direction or push is pressed | `cursor.previous`, `cursor.next`, `page.previous`, `page.next`, `chain.previous`, `chain.next`, `transport.back`, `transport.forward` |
| `KNOB TURN` | A knob is turned | `cursor.follow` |
| `KNOB TOUCH` | A knob is touched | `cursor.follow` |

Every input also accepts `default` and `none`.

What the actions do:

| Action | Meaning |
|---|---|
| `default` | The original handling of this input, as if no binding matched. |
| `none` | Do nothing. The release is swallowed too. |
| `cursor.edit` | Change the parameter under the cursor, the same as turning its knob. Not applicable when there is no cursor cell. |
| `cursor.previous` | Move the cursor to the previous filled cell. Past the first one, go to the neighbouring page. |
| `cursor.next` | Move the cursor to the next filled cell. Past the last one, go to the neighbouring page. |
| `cursor.follow` | If the knob's cell is filled, move the cursor to it. The knob then still turns or highlights as usual. |
| `edit.knob1`, `edit.knob2`, `edit.knob3`, `edit.knob4`, `edit.knob5`, `edit.knob6`, `edit.knob7`, `edit.knob8` | Change the parameter of that cell, the same as turning that knob. Not applicable when the cell is empty. |
| `page.previous` | Go to the previous parameter page, like PAGE LEFT. |
| `page.next` | Go to the next parameter page, like PAGE RIGHT. |
| `chain.previous` | Switch to the previous chain slot. Not applicable outside `SAMPLER`, `PLUGIN` and `AUDIO LOOP`. |
| `chain.next` | Switch to the next chain slot. Not applicable outside those pages. |
| `transport.move` | The original 4D turn on the current page (for example, moving the playback position). |
| `transport.back` | One step back, like the original 4D up on a non-chain page. |
| `transport.forward` | One step forward, like the original 4D down on a non-chain page. |

"Not applicable" means the input gets the original handling, the same as `default`. Later bindings are not tried.

The bar under the cursor cell is drawn only where the active profile has a `cursor.` binding that applies to the current page and cursor condition. SHIFT is ignored for this, so the bar does not flicker.

## Matching

- The first binding in the file that matches the input and all of its `pages`, `shift` and `cursor` conditions wins. Put specific bindings before broad ones.
- If nothing matches, the original handling runs.
- While a VOLUME, SWING or TEMPO master mode is on (its button is lit), profiles are not used.
- Profiles apply only on the parameter pages. Other pages always keep the original behaviour.
- During a software update, profile actions do nothing, like the original handling.

Press ownership: the 4D directions, 4D push and the knob touches decide at the moment of the press who handles them, and the release goes to the same handler. Changing SHIFT, the page or the profile between press and release does not change that. A profile action runs once per press, even if the controller reports the press again.

## Errors

The journal shows why a file was skipped. On the device:

```
journalctl --user -u machinista
```

- `PROFILE NOT FOUND` is shown when the saved profile is missing or invalid. The controller uses Original. Your choice is kept, so the profile returns when you fix the file and reopen the CONTROLLER PROFILE page.
- `PROFILE ERROR` is shown when an action fails. The event is dropped, the details go to the journal, and the controller keeps running with the profile still selected.

## Compatibility promise for format 1

Within `format: 1`, an existing input, condition, group or action name never changes meaning and is never removed. New ones may be added. A file using a name this Machinista does not know (input, page, group, action or key) is rejected whole. For an unknown action, the message says it may be misspelt or added in a newer Machinista. Only a higher `format` is reported as needing a newer Machinista. Original always means the current Machinista behaviour.

## Examples

### The built-in 4D cursor profile

4D turn edits the parameter under the cursor. 4D left and right move the cursor. Turning a knob moves the cursor to it.

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

### 4D turn edits knob 1

```json
{
  "format": 1,
  "name": "4D edits knob 1",
  "device": "mk3",
  "bindings": [
    {"input": "4D TURN", "shift": false, "action": "edit.knob1"}
  ]
}
```

### 4D push goes to the next page

```json
{
  "format": 1,
  "name": "4D push next page",
  "device": "mk3",
  "bindings": [
    {"input": "4D PUSH", "action": "page.next"}
  ]
}
```
