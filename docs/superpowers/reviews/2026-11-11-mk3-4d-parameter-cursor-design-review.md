# Review — MK3 4D-encoder parameter cursor design

Reviewed: 2026-11-11
Source: [design specification](../specs/2026-11-11-mk3-4d-parameter-cursor-design.md)
Verdict: **Approve with revisions** (design review; not an implementation review).

## Findings

### P1 — Cursor identity is not scoped to the edited target

The key `(page, control_level, page_index)` distinguishes page layouts but not the selected sound/pad, group, plug-in instance, or chain slot. In particular, `PLUGIN` uses `plugin_param // 8` as its page index, so two different plug-ins on page zero share a cursor even when their controls have different meanings. `SAMPLER` and channel-level views can similarly inherit positions from other targets.

Specify whether cursor memory is intentionally per *layout* or per *parameter target*. If the latter, include stable target identity (and plug-in identity/slot as appropriate) in the key, with clear invalidation when targets are deleted/reordered. Add tests switching between two plug-ins with different control layouts and between sounds.

### P1 — Navigation across pages with no populated fields is undefined

The design says an empty page has no cursor and 4D turn falls back to old behavior. But it also says left/right traverse the current page and wrap using `change_page()`. What happens when the destination page is empty? Should another left/right press advance, should the cursor remain absent, or should navigation skip empty pages? A single `change_page(+/-1)` can also move between different page names via `channel_page_path()`.

Specify an explicit, bounded traversal algorithm that handles empty destinations and page changes, detects when `change_page()` did not advance, and does not loop. Test sparse pages and cross-page transitions, including a destination with zero populated cells.

### P1 — SHIFT + cursor left/right behavior needs an explicit contract

The spec reserves SHIFT + 4D *turn* for the previous transport behavior but says 4D left/right always move the cursor on active pages. Existing `change_page()` and other navigation paths are shift-aware. State explicitly whether SHIFT + MASTER LEFT/RIGHT should still move the cursor, retain previous shifted navigation, or do something else. This matters especially at page boundaries, where cursor navigation invokes `change_page()`.

Add SHIFT + left/right tests at interior cells and at both page boundaries.

### P2 — Clarify how cursor ownership interacts with master modes and knob edits

The spec says master modes take precedence, but the implementation sketch puts the cursor interception in `Mk3Surface.rotate()`. The inherited `Mk2Surface.rotate(0, delta)` has an explicit `master_mode` branch, and `Mk3Surface.button()` also routes MASTER UP/DOWN to `rotate(0,...)`. Ensure the cursor predicate checks the actual master-mode state and that a physical 4D turn is distinguishable from synthetic `rotate(0,...)` invocations where necessary. A cursor should not unexpectedly capture unrelated master/navigation operations.

Add tests for VOLUME, SWING, and TEMPO and for MASTER UP/DOWN on a cursor-active page, not just held TEMPO.

### P2 — Define behavior when turning an empty knob cell

The spec says turning knob n sets the cursor to n−1 *before* the value changes, but also promises that the cursor always resolves to a populated cell. The inherited `rotate()` exits without editing when `fields()[index-1] is None`. Specify whether an empty-cell turn leaves the cursor unchanged or records a stale index to be resolved to the nearest field. Prefer no cursor change for a knob with no binding, and test it.

### P2 — Cursor display and touch underline can be visually indistinguishable

The proposed rendering draws the same 2-pixel accent underline for both persistent cursor and temporary knob touch. When they refer to different cells, both cells look selected; when they coincide, the visual state does not distinguish the two. This may be acceptable, but should be an explicit UI choice. Consider a persistent cursor indicator distinct from touch (or document the intentional equivalence), and test snapshots for both states.

### P2 — Specify and test batched encoder deltas

The goal says one detent equals one step, but `rotate(cursor+1, delta)` passes the raw delta through. Verify the MK3 input path reports detents as the intended signed integer delta and that a batched `delta` of magnitude greater than one produces the expected number of parameter steps, subject to existing per-field scaling and clamping. Test positive, negative, and multi-step deltas on discrete and continuous fields. Do not assume every existing knob field has a unit quantum.

## Positive aspects

- Restricting behavior to the MK3 rather than changing the shared MK2 engine reduces regression risk.
- Reusing the existing knob rotation path should preserve editing, automation, undo, and feedback semantics.
- Resolving cursor positions against live `fields()` avoids stale indexes causing out-of-range edits.
- Keeping the cursor ephemeral is appropriate for a navigation affordance.
- Explicit PlusSurface regression coverage and hardware acceptance testing are good requirements.

## Recommended acceptance additions

1. Switch among two different plug-in instances, sound/pad targets, and chain slots; verify cursor identity is intentional.
2. Traverse populated/empty views in both directions, including the multi-page CHANNEL path and first/last boundary.
3. Exercise SHIFT + LEFT/RIGHT, SHIFT + turn, and all three master modes.
4. Turn an unbound knob; verify the cursor and edited parameter remain sensible.
5. Test delta ±1 and ±N, discrete and continuous parameters, and clamping.
6. Render touch-only, cursor-only, and simultaneous touch/cursor display states.

These findings are based on the specification and the current `mk3_surface.py`, `mk2_surface.py`, `mk3_session.py`, and `mk3_display.py` control paths. No implementation changes or tests were run as part of this review.
