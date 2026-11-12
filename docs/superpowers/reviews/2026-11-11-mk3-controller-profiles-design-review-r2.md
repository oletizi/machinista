# Follow-up design review — MK3 controller profiles (revision 2)

Reviewed: 2026-11-11
Spec blob: `210ef8272f26ac0fdd9aeba01b3e3c5445e9bd5a`
Spec: [MK3 controller profiles](../specs/2026-11-11-mk3-controller-profiles-design.md)

**Verdict: APPROVED FOR IMPLEMENTATION, with minor specification clarifications.**

The revision resolves the three prior P1 issues:

1. **Original semantics:** The original profile now means an empty binding set over an explicitly profile-free MK3 control path, rather than falling through to cursor-aware handlers. The pre-cursor baseline (`cebddb3`) is identified for regression testing.
2. **Single dispatch:** Physical events enter through `physical_button`, `physical_rotate`, or `physical_turn`; actions call non-dispatching `button`/`rotate` operations. This avoids recursive profile evaluation.
3. **Press/release ownership:** Every intercepted button gets an owner at press time, with handling defined for default, none, not-applicable, cursor.follow, and SHIFT/page/profile changes before release. Touch-release behavior is now consistent.

The former P2 findings are also addressed: the cursor indicator is scoped to applicable pages and cursor state, profile identifiers are stable filename stems, validation and action errors are handled separately, and group/list matching plus first-match fallthrough are specified.

## Non-blocking clarifications

### P2 — Compatibility wording contradicts unknown-name validation

The revised validation section correctly says an unknown action may be misspelled **or** introduced in a newer version, and only a higher `format` definitively requires newer Machinista. The Compatibility promise still states that any unknown name is rejected with `needs a newer Machinista`. Align this wording with the validation contract so diagnostics do not incorrectly classify typos as version incompatibility.

### P2 — Record press ownership before executing a potentially failing action

The error-handling section says a raised action consumes the event with owner `profile`, but the press-ownership definition says `profile` when the matched action **ran**. Make the ordering explicit: once a matching, applicable profile action is chosen, record/retain `profile` ownership before invoking it (or in a `finally` path), including if the action throws after partially mutating state. Otherwise the subsequent release may reach the original handler and violate the no-double-effects policy. Add a test that raises during a button action and then releases after SHIFT or page changes.

## Implementation verification

Ensure the base session's button delivery and quantized knob delivery are both switched to the physical-input hooks, while synthetic surface calls continue to bypass matching. Verify PlusSurface/PlusSession continue to use the pass-through implementation. The expanded test plan is appropriate.

**No blocking findings remain.** This is a design/source review; implementation and hardware tests were not run.
