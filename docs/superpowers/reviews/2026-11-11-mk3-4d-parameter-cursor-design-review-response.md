# Response to review — MK3 4D-encoder parameter cursor design

Responds to: [design review](2026-11-11-mk3-4d-parameter-cursor-design-review.md)
Spec revised in the same commit.

## P1 — Cursor identity not scoped to the edited target

**Partly disagree.** Per-layout memory is intentional, not an oversight. On
Sampler and Channel views, the same cell is the same parameter for every sound
and group; keeping the position when the user moves from pad 1 to pad 2 is the
useful behaviour (it lets them edit one parameter across sounds). Per-target
memory would reset or scatter the cursor every time the selection changes.

**Agreed for plug-ins:** different plug-ins put different parameters in the same
cell, so the key now includes the selected plug-in's URI on `PLUGIN`. Separate
instances or slots of the same plug-in deliberately share a position (same
layout). No invalidation is needed because positions resolve against the live
`fields()` on every use, as the review notes. Tests added: two plug-ins keep
separate positions; two sounds share one.

## P1 — Navigation across empty pages undefined

**Agreed.** The spec now defines a bounded traversal: at most `page_total` calls
to `change_page()`, stop when the view key does not change, land on the first
populated view, and restore the original view if none is found. Page-name
changes via `channel_page_path()` are covered by including the page name in the
key. Tests added for sparse pages, the multi-page CHANNEL path in both
directions, and a destination with no populated cells.

## P1 — SHIFT + left/right contract

**Agreed.** SHIFT + left/right now explicitly keeps the pre-cursor behaviour
(chain-slot switching on Sampler / Plug-in / Audio Loop, NAV elsewhere),
matching SHIFT + turn. Tests at an interior cell and both boundaries.

## P2 — Master modes and synthetic `rotate(0, …)`

**Agreed, and this one was a real bug in the sketch.** `Mk3Surface.button()`
routes MASTER UP/DOWN on non-chain parameter pages to `rotate(0, ±1)`, so
intercepting `rotate(0)` would have turned 4D up/down into parameter edits. The
physical turn now has its own entry point, `master_turn()`, called from
`Mk3Session.rotate_raw(0)`; `rotate(0)` is unchanged. Tests now cover VOLUME,
SWING and TEMPO and MASTER UP/DOWN on a cursor page.

## P2 — Turning an empty knob cell

**Agreed.** Turning a knob whose cell is empty leaves the cursor unchanged.
Tested.

## P2 — Cursor and touch indicators indistinguishable

**Agreed.** The cursor is now a 3-pixel bar below the cell; touch keeps its
2-pixel line above it. Render tests cover touch only, cursor only and both.

## P2 — Batched encoder deltas and per-field quantum

**Disagree with the premise; tests added anyway.** The quantum concern does not
apply at this layer. `Mk2Surface.rotate(index, delta)` takes *steps*: for
knobs, `Mk2Session.rotate_raw` divides raw 0–999 counts by each field's quantum
before calling it. The 4D counter (0–15) reports one count per detent, and
`rotate_raw(0, …)` forwards it unscaled. Passing a 4D delta of N into
`rotate(cursor + 1, N)` is therefore exactly N field steps, whatever the field's
quantum. The ±1 / ±N tests on discrete and continuous fields, including
clamping, are cheap and now in the plan, to pin this down.

## Acceptance additions

All six are reflected in the revised test list. For item 1, chain slots are
covered through the plug-in URI case; slot-for-slot identity is intentionally
not distinguished (see P1).

## Revision 2 response

Responds to: [follow-up review](2026-11-11-mk3-4d-parameter-cursor-design-review-r2.md)

**P1 — rollback after empty-page traversal: agreed on the problem, resolved by
removing the rollback rather than completing it.** `change_page()` does mutate
more than the five saved fields, so a partial restore could leave the page and
editing target inconsistent. A complete restore would mean reversing every side
effect of `change_page()`, and keeping that in step with future changes to it.
Instead, the traversal now never rolls back: each step is an ordinary
PAGE LEFT/RIGHT page change, so the result is always a state the page buttons
can already produce. If no populated view remains, the user lands on the last
empty view with no cursor, exactly as after pressing PAGE RIGHT there. The test
compares the full navigation and editing state with a twin application that
pressed the page buttons the same number of times.

**Minor — `rotate_raw` delegation: agreed.** The override intercepts only
index 0; indices 1–8 go to `super().rotate_raw()`. The turn tests now go through
`Mk3Session.rotate_raw(0, delta)`.
