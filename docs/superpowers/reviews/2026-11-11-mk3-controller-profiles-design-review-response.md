# Response to review — MK3 controller profiles design

Responds to: [design review](2026-11-11-mk3-controller-profiles-design-review.md)
Spec revised in the same commit.

## P1 — Empty Original does not restore pre-cursor behaviour

**Agreed on the wording, not on the premise.** The spec already moved the
cursor logic out of `mk3_surface.py` into `mk3_actions.py` and replaced the
cursor code at the entry points, so "original handling" was never meant to be
the cursor branch's `button()`/`rotate()`. That was implicit, though, and the
review is right that it must be explicit. The spec now has an "Original
handling" section: it is the profile-free surface path with every cursor
interception removed (`MASTER LEFT/RIGHT` and `cursor_buttons` in `button()`,
cursor recording in `rotate()`, `master_turn()`), whose logic then exists only
behind profile actions.

On the baseline: Original means **current upstream MK3 behaviour**, tracking
future upstream changes, not a frozen snapshot. That is the reason for defining
it as "no bindings" over the unmodified path rather than as a re-implementation.

Testing: agreed to test against the real pre-cursor behaviour. A twin
comparison against old code is not possible in one tree, so the check is that
every `tests/test_mk3_*.py` file as it was at `cebddb3`, before the cursor
branch, passes unchanged with Original selected.

## P1 — Recursive dispatch

**Agreed; this was a real hole.** Naming `rotate()` as both an action target
and a dispatch entry point would have re-dispatched `edit.knobN` as a
`KNOB TURN`. The spec now has a "Dispatch boundary" section. Matching happens
once, where the session delivers the physical event: new
`physical_button`/`physical_rotate` hooks at the two existing call sites in
`Mk2Session` (`app/mk2_session.py:119` and `:157`), pass-through for other
controllers, and `physical_turn` from `Mk3Session.rotate_raw(0)`. `button()`
and `rotate()` never consult a profile, so actions and synthetic callers
(MASTER UP/DOWN → `rotate(0, ±1)`) cannot re-enter. Tests for
`4D TURN → edit.knob1` and `KNOB TURN → cursor.follow` assert one dispatch and
one edit.

## P1 — Release ownership

**Agreed.** New "Press ownership" section. Every intercepted button gets an
owner (`profile` or `original`) at press time, covering `default`, `none`,
not-applicable, unconsulted cases and `cursor.follow`. The release goes to the
owner: `original` gets `button(name, False)` exactly as today, so `held`,
`touched` and other release effects stay intact. SHIFT, page, profile or file
changes between press and release cannot move it. Disconnect clears owners. The
`KNOB TOUCH` contradiction is resolved by dropping the special case: touch
follows the same rule, so `none` consumes both press and release and
`cursor.follow` leaves both to the original handler. Tests cover each case.

## P2 — Cursor indicator

**Agreed; current-context predicate chosen.** The bar shows when the view has
a cursor cell and the profile has a `cursor.*` binding whose `pages` and
`cursor` conditions hold here, with no master mode held. `shift` is
deliberately ignored for this test so that pressing SHIFT does not make the bar
flicker. Tests cover a page-limited binding, SHIFT held and Original.

## P2 — Safety and compatibility claims

**Agreed the claim was too strong.** The spec now defines the action boundary:
- Each action checks its own preconditions and reports "not applicable".
- If an action raises anyway, the error goes to the journal with the profile,
  binding and input, the display shows `PROFILE ERROR`, and the event is
  consumed. It deliberately does not fall back to the original handling,
  because a half-applied action followed by the original one could produce two
  edits.
- Loading never raises, so a bad user file cannot break start-up or the
  settings page.

On messages: only `format > 1` is reported as definitely needing a newer
Machinista. An unknown name is reported as "misspelt, or added in a newer
Machinista".

## P2 — Name as persistence identifier

**Agreed; identifier introduced, using the file name.** A profile's identifier
is its file name without `.json` (`[a-z0-9][a-z0-9-]{0,31}`; the built-ins are
`original` and `cursor`). The selection stores the identifier, so editing the
display name keeps the selection. Renaming the file makes it a new profile;
that is now written into the format-1 contract. I did not add a separate `id`
key inside the file: a second identifier that could disagree with the file name
adds a failure mode without a benefit, since a folder cannot hold two files
with the same name. Display names no longer need to be unique.

## P2 — Matching and page/group semantics

**Agreed.**
- `pages` accepts a list mixing page and group names.
- A not-applicable action gets the original handling and later bindings are
  **not** tried. This is now stated explicitly.
- Tests were added for:
  - overlapping broad and specific rules, in both orders;
  - omitted conditions;
  - group expansion;
  - mixed lists;
  - a not-applicable action followed by a later binding that would have
    matched.

## Revision 2 response

Responds to: [follow-up review](2026-11-11-mk3-controller-profiles-design-review-r2.md)

**P2 — compatibility wording: agreed.** The compatibility promise now uses the
validation section's wording: an unknown name is reported as "misspelt, or added
in a newer Machinista"; only a higher `format` is reported as needing a newer
Machinista.

**P2 — ownership before a failing action: agreed.** The plan already had this:
`dispatch()` catches the error and returns `profile`, and that result becomes
the press owner. The spec now states it: the owner is `profile` once an
applicable action is chosen, whether it completes or raises. The plan adds
`test_failed_button_action_keeps_profile_ownership`, which raises during a
`MASTER RIGHT` action and releases after SHIFT and the page change, and asserts
that the original release handler is never reached.

**Implementation verification:** these items are covered in the plan.
- Task 2 switches both `Mk2Session` delivery sites (button events and quantised
  knob steps) to the `physical_*` hooks.
- `test_plus_ignores_profiles` covers Plus surfaces and sessions.
- `test_turn_edit_knob1_dispatches_once_and_edits_once` covers synthetic calls
  bypassing matching.
