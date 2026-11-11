# Implementation plan review — MK3 4D parameter cursor

Reviewed: 2026-11-11
Plan: [2026-11-11-mk3-4d-parameter-cursor.md](../plans/2026-11-11-mk3-4d-parameter-cursor.md)
Plan blob: `4b44c3c8c15111bd829f2d10837c5524e45b26ab`
Design: [approved specification](../specs/2026-11-11-mk3-4d-parameter-cursor-design.md)

**Verdict: CHANGES REQUESTED.** The four-task decomposition and reuse of the existing knob path are good, but Task 2 has two navigation correctness problems.

## P1 — Traversal bound is insufficient across the channel path

Task 2 sets `total=max(1,min(16,self.page_state()[1]))` and uses `for _ in range(total)`. For INPUT/GROOVE/MACRO, `page_state()` falls back to `(0,1)`, although `change_page()` traverses the longer `channel_page_path()` containing INPUT, multiple CHANNEL pages, GROOVE and MACRO. Therefore the loop can terminate after a single empty view, before reaching a populated one. Reassigning `total` inside the `for` loop does **not** change the iteration count.

**Fix:** Determine the traversal bound from the actual navigation domain (e.g. `len(channel_page_path())` for channel pages, page count otherwise), or use a fixed safe cap with visited-key detection and stop-on-no-change. Cover traversal across multiple consecutive empty views, both directions, starting at INPUT and GROOVE.

## P1 — No-cursor views cannot necessarily be exited via cursor navigation

The Task 2 interception condition is `self.cursor_cell() is not None`. The approved design permits traversal to terminate on an empty page, with no cursor, and says the opposite direction moves back. But with the proposed handler, the opposite left/right press falls through to the old `MASTER LEFT/RIGHT` mapping rather than `move_cursor()`. This is particularly problematic on empty INPUT/GROOVE/MACRO views.

**Fix:** Define a consistent policy for empty cursor pages. Preserve the explicit legacy exception for a PLUGIN page without controls, but allow cursor-page navigation to move out of other empty views (or change the spec to guarantee no empty endpoint). Add a test that navigates into an empty endpoint and then returns using the opposite 4D direction. This also needs an explicit rule for where to start when no cell is selected.

## P2 — Several listed tests are comments, not runnable tests

Task 2 and Task 3 include `def test_...():` with comment-only bodies. The instruction to fill them in is helpful, but the plan is not fully executable as written; an agent copying those snippets verbatim gets invalid Python. Replace placeholders with complete tests, or mark them clearly as pseudocode and require executable assertions before each implementation step. Especially important are empty-page traversal and display pixel tests.

## P2 — Test fixtures may not represent equivalent editing state

The `twin()` helper copies the project, `page`, and `control_level`, but not page-specific selectors such as `channel_page`, `plugin_param`, `sampler_page`, selected pad/slot, or field selections. This can make the comparison between 4D edits and knob edits invalid or vacuous. Build twins from equivalent relevant application state (or explicitly set every selector needed for each test). In the plugin-layout test, `Field('x',())` also appears inconsistent with the `Field(label, value, attrs)` constructor used in `mk2_surface.py`; use valid field fixtures.

## P2 — Verify source gating at the session entry point

The global constraint says PlusSurface must retain existing behavior. The plan correctly gates cursor state by `source == 'mk3'`, but Task 3 overrides `Mk3Session.rotate_raw()`. Verify that the Plus session path inherits this override safely: `master_turn()` must exist on its surface (it should, as PlusSurface subclasses Mk3Surface), and source gating must cause the original `rotate(0,delta)` path. Include an integration-level Plus session test, not only a surface-level cursor test.

## Positive aspects

- Physical 4D turn interception is separate from synthetic `rotate(0,...)` calls.
- Smooth knob accumulation is preserved by delegating indices 1–8 to the parent session.
- Discrete/continuous, multi-detent, master mode, touch/cursor rendering, and hardware acceptance are covered in the intended test matrix.
- Incremental commits and targeted regression suites are sensible.

**Recommendation:** Fix the two P1 navigation cases and strengthen the test fixtures before execution. No implementation or hardware tests were run as part of this review.
