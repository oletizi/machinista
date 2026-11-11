# Response to implementation plan review — MK3 4D parameter cursor

Responds to: [plan review](2026-11-11-mk3-4d-parameter-cursor-implementation-plan-review.md)
Plan and spec revised in the same commit.

## P1 — Traversal bound insufficient across the channel path

**Agreed; both defects are real.** `page_state()` returns a total of 1 for
INPUT, GROOVE and MACRO, and reassigning `total` inside the `for` loop had no
effect. The bound is now `len(channel_page_path())` when that path exists, else
the page count, clamped to 1–32, plus a visited-key set that stops on no change
or a cycle. The spec states the same rule. New test: consecutive empty CHANNEL
pages skipped starting from INPUT (right) and from GROOVE (left).

## P1 — No-cursor views cannot be exited

**Agreed.** Policy now in spec and plan: on an empty view, left/right without
SHIFT still navigate. On chain pages (Sampler, Plug-in, Audio Loop) they keep
switching slots, so a plug-in without controls can always be left; on the other
cursor pages they run the page traversal immediately, so the first move from an
empty view goes straight to the neighbouring populated page (landing on its
first cell moving right, last moving left). The endpoint test now walks into an
empty endpoint and back out with the opposite direction.

## P2 — Comment-only tests

**Agreed.** Every test in the plan is now complete, runnable code.

## P2 — Twin fixtures may not represent equivalent state

**Agreed on the risk; fixed differently.** Instead of copying more selectors
into a second application, the edit-equivalence tests now replay on the *same*
application: snapshot the project, apply the knob step, record the result,
restore the snapshot, apply the 4D step, compare. Every selector is identical by
construction, and the helper reports whether the step changed anything so
the tests can assert they are not vacuous. A second application remains only
where the comparison is navigation state, not edits (page-button equivalence
and SHIFT legacy behaviour), and there every compared selector is set
explicitly. The `Field` fixture now uses the real `(label, value, attributes)`
constructor.

## P2 — Source gating at the session entry point

**Agreed.** `PlusSession` subclasses `Mk3Session`, so it inherits the
`rotate_raw` override; `master_turn` exists on `PlusSurface` and returns to
`rotate(0, …)` because `cursor_cell()` is `None` for source `plus`. Added an
integration test through `PlusSession.rotate_raw(0, 1)` asserting the transport
still moves and the project is unchanged.
