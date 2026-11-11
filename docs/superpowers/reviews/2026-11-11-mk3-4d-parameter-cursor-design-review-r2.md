# Follow-up review — MK3 4D-encoder parameter cursor (revision 2)

Reviewed 2026-11-11. Design blob: `ea2297da2716d9c20adefce16c23108605538adc`.

**Verdict: Approve with one required correction.**

The revision addresses the original seven findings: per-layout cursor identity is now intentional (and PLUGIN is keyed by URI), physical 4D input has a dedicated `master_turn()` entry point, SHIFT navigation is specified, empty knob cells are ignored, cursor/touch markers differ, batched deltas are defined, and the tests cover these contracts. The distinction between physical `master_turn()` and synthetic `rotate(0, ...)` is especially valuable.

## Remaining finding

### P1 — Empty-page traversal cannot safely restore only the listed view fields

The new algorithm saves `(page, channel_page, sampler_page, plugin_param, control_level)`, calls `change_page()` repeatedly, and restores that tuple if no populated destination is found. But the existing `Mk2Surface.change_page()` mutates additional application state: the `channel_page_path()` branch changes `parameter_kind`, `parameter_choice`, field selection (e.g. `channel_field`, `input_field`, `groove_field`, `macro_index`), and invokes `remember_control_view()`. Other page branches likewise modify page-specific selections. Reassigning the saved tuple does not reverse those effects, potentially leaving the visible page and editing target inconsistent.

**Required change:** Specify a non-mutating traversal of candidate views, or a complete, side-effect-safe restoration strategy. Do not assume that saving the five named fields is sufficient. Test a traversal that crosses the CHANNEL path through empty views, finds no populated destination, and verifies *all* relevant navigation/editing state (including parameter choice and remembered view), not just the page label.

## Minor implementation clarification

The proposed `Mk3Session.rotate_raw()` override should delegate indices 1–8 to `super().rotate_raw(index, delta)` so the inherited smooth-knob accumulator and field quantum remain intact. Intercept only index 0. Add an integration-level test through `Mk3Session.rotate_raw(0, delta)` rather than testing `master_turn()` alone.

Once the rollback contract is corrected, I see no further design-level blockers. This is a specification review; no code was changed or tests executed.
