# Follow-up implementation plan review — revision 2

Reviewed 2026-11-11
Plan blob: `8c729c5999bd40212bdcbd7a43c1cca2c7bf1d28`
Plan: [MK3 cursor implementation plan](../plans/2026-11-11-mk3-4d-parameter-cursor.md)

**Verdict: APPROVED FOR IMPLEMENTATION, with minor test corrections recommended.**

Both previous P1 navigation findings are addressed. Traversal now derives its bound from `channel_page_path()` where applicable, uses visited view keys, and handles empty non-chain parameter pages without trapping the user. Empty chain pages intentionally retain legacy slot switching. The revised plan also includes concrete test bodies, a more reliable same-application comparison helper, and a PlusSession integration check.

## Non-blocking test corrections

### P2 — Verify the expected knob cursor explicitly in the equivalence helper

`same_as_knob(knob,delta,action)` relies on `self.s.rotate(knob,delta)` to set the cursor, then restores the project before calling `action()`. This is valid for a populated knob on a cursor-active page, but can silently test the wrong binding if a fixture changes or the knob is empty. Add `assertEqual(self.s.cursor_cell(), knob-1)` before invoking the action, and use a parameter known to change when `assertTrue` is required.

### P2 — Strengthen the accumulator test

`test_session_knobs_still_use_accumulator` asserts that a single raw count on CHANNEL knob 3 produces no `surface.rotate()` call. That only holds if the field's actual `quantum()` is greater than one. Compute/verify the field quantum in the test, then send `quantum-1` counts (no rotation) followed by one count (exactly one step). This tests preservation of accumulated travel, not just suppression of a single count.

### P2 — Ensure the empty-endpoint regression compares equivalent initial state

`test_empty_endpoint_matches_page_buttons_and_can_be_left` creates a new `Application` for the PAGE-button comparison. Initialize its relevant project and selectors from the same starting state as the tested application, or the state comparison may be affected by fixture defaults rather than the navigation operation. The existing assertion on `control_views` is valuable; retain it.

## Positive findings

- The visited-key guard and channel-path bound resolve the earlier premature traversal problem.
- The button handler explicitly allows leaving empty non-chain pages while preserving legacy behavior on empty chain pages.
- The PlusSession test checks that the inherited session override still routes to transport.
- The display test exercises both marks and the actual update snapshot.
- Task-by-task tests, commits, and hardware acceptance are appropriately scoped.

No blocking findings remain. This is a plan review; implementation tests and MK3 hardware verification have not been performed.
