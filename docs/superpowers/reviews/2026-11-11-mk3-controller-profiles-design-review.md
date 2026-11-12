# Design review — MK3 controller profiles

Reviewed: 2026-11-11
Spec blob: `5fae324983ffba25ac6b1246f6b915d0754b17c6`
Spec: [MK3 controller profiles design](../specs/2026-11-11-mk3-controller-profiles-design.md)

**Verdict: CHANGES REQUESTED.** The bounded, declarative action vocabulary and strict validation are sound. The following dispatch contracts should be resolved before implementation.

## P1 — An empty Original profile does not automatically restore pre-cursor MK3 behavior

The source branch already has cursor-aware `Mk3Surface.master_turn()`, `rotate()`, and `button()` handling. The spec defines Original as `bindings: []` and says unmatched/default events use "original handling." If default simply falls through to these existing methods, Original will still edit the cursor and intercept left/right. Specify an explicit, profile-independent **legacy handler** for each intercepted input (or an equivalent refactor that removes cursor interception from the underlying path). Test Original against the actual pre-cursor behavior, not against whatever the refactored dispatcher currently does. Also clarify whether the baseline means behavior before the cursor feature or current upstream behavior at the time of a future release.

## P1 — Action execution can recursively enter profile dispatch

`cursor.edit` and `edit.knobN` invoke `rotate(n,delta)`, `transport.move` invokes `rotate(0,delta)`, and `cursor.follow` continues into the original knob handler. Yet `rotate()` and `master_turn()` are named profile dispatch entry points. Define a clear dispatch boundary: profile matching happens once at the physical-input boundary; actions invoke undecorated, non-dispatching operations (or an explicit bypass path), preserving existing undo, automation, quantization and display semantics. Test a custom 4D TURN → edit.knob1 profile and a KNOB TURN → cursor.follow profile to ensure exactly one edit and no recursive dispatch.

## P1 — Release ownership must cover all intercepted buttons and press-time context

The spec promises that a release goes to the handler that took the press, even if SHIFT or page changes. The existing `cursor_buttons` mechanism only covers left/right. The new dispatcher covers UP/DOWN/PUSH and KNOB TOUCH as well. Specify press ownership for **every** intercepted button, including when a binding resolves to `default`, `none`, or a not-applicable action, and when a profile is changed/reloaded while a button is held. Preserve `self.held` and any original input release effects. The statement that `none` swallows releases conflicts with the unconditional rule that KNOB TOUCH releases always take original handling; explicitly resolve that exception. Test SHIFT/page/profile changes between press and release.

## P2 — Profile selection and cursor display need a precise visibility contract

"Draw the cursor bar when the profile has at least one `cursor.*` binding" is broader than actual cursor applicability. A profile can bind cursor actions only on a subset of pages, or only with SHIFT, while the bar remains visible elsewhere. Specify whether the bar denotes a cursor-capable profile or an *active* cursor binding in the current context. Prefer an explicit, current-context indicator predicate; otherwise document the intentionally persistent indicator and test it.

## P2 — Clarify the safety and compatibility claims

Validation can reject unknown data, but the claim that validation is the **only** defense and a loaded profile cannot raise unexpectedly is too strong. Valid action names can encounter unavailable targets, state transitions, and handler errors. Define safe failure behavior at the action boundary (including not-applicable fallthrough), and ensure bad user profiles cannot make controller startup or profile selection fail. Also distinguish "unknown name needs a newer Machinista" from ordinary misspellings: the former is not provable for arbitrary unknown names.

## P2 — Profile name is a fragile persistence identifier

Selection persists a case-insensitive display name. Renaming a user profile, or a future built-in name collision, changes selection identity. The fallback is described, but a stable machine identifier separate from the 24-character display name would improve forward compatibility. Either introduce one now or explicitly accept rename-as-new-profile semantics in the format-1 contract.

## P2 — Validate ambiguous matching and page/group semantics

First-match precedence is specified, which is good. Add explicit tests for overlapping broad/specific rules, omitted conditions, group expansion, mixed page-name lists, and non-applicable actions falling through to original handling **without trying later bindings**. Also specify whether `pages` accepts a list containing group names, or only explicit page names; the current wording leaves that unclear.

## Strengths

- Declarative JSON and a closed action set avoid executable configuration.
- Validation is all-or-nothing and file loading is bounded by size and type.
- Device scope protects Maschine+ and other surfaces.
- Original and Cursor as built-ins are useful regression fixtures.
- First-match ordering and press/release ownership are appropriate foundations.
- Startup and settings-page reload are reasonable for device-local workflows.

**Recommendation:** Resolve the legacy dispatch path, non-recursive action execution, and full release ownership before approving the design. The remaining issues can be handled as clarifications, but should be settled before freezing format 1.

This is a spec/source review, not an implementation test. No code or hardware tests were run.
