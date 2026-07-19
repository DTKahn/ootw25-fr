# Review App UI Pass — Design Spec

Date: 2026-07-19
Status: Approved

## Purpose

The review app (`review-app/`) is live and being used, but the initial build was scoped tightly to functional correctness, not visual polish. This pass addresses seven concrete UI/UX issues raised after real usage, plus a general cleanup, on `app/review/page.tsx`.

## Calibration

This is a dense, single-reviewer data tool, not a branded/marketing page. The design direction favors clarity and information density over visual flourish — no hero moment, no new typefaces, no decorative motion. The one deliberate structural device introduced here is the status color system: it's functional (at-a-glance review progress), not decorative.

## Changes

1. **Status column first.** Currently last; moves to the first column so scanning down it shows review progress across all rows at a glance.
2. **Wider Reviewer French / Notes columns.** Currently auto-sized by the browser's table layout and end up cramped. Switch to a fixed table layout with explicit column-width allocation, giving these two the most space (they're where the reviewer actually works).
3. **General visual cleanup**, scoped to:
   - Consistent spacing/padding across cells and controls
   - A bordered card container around the table (continuing the visual convention from the original review artifact, `scripts/build_artifact.py`)
   - Row hover highlight for easier scanning
   - Explicit type scale: 1.25rem/600 page title, 0.875rem table body, 0.75rem meta text (ids, save-state messages)
   - Sticky filter bar (page/status/search/export controls stay visible while scrolling)
4. **"Use suggested" button.** A button next to the Reviewer French textarea that copies `suggestedFrench` into the reviewer's editable field (same code path as manual typing — see auto-status rule below).
5. **Rename "Your French" → "Reviewer French"** in the column header (and the `Row` type's field is already named `reviewerFrench`, no data-layer change needed).
6. **Auto-status rule.** Whenever the Reviewer French field's content changes (typed manually or via "Use suggested"):
   - Non-empty → status is set to `changed`, unconditionally (overrides any prior status, including `flagged`)
   - Empty → status is set to `not_reviewed`
   - This only fires on edits to the Reviewer French field itself — manually selecting a status via the dropdown (e.g. `approved` or `flagged` while the field stays empty) is unaffected and persists normally.
7. **Color-coded statuses.** Status is rendered as a colored pill/badge (in both the status-select control's context and anywhere else status appears) using a semantic, light/dark-aware palette:
   - `not_reviewed` → gray (neutral)
   - `changed` → blue (reuses the existing "differs from live" blue already used elsewhere in this app, for visual consistency)
   - `approved` → green
   - `flagged` → red

## Non-goals

- No changes to the data model, API routes, auth, seed pipeline, or CSV export — this is a `app/review/page.tsx`-scoped UI pass (plus a small extracted styles module, see File structure).
- No new dependencies (no component library, no CSS framework) — continues the existing inline-style approach, just better organized.
- No automated tests — this remains UI code verified manually, consistent with the original build's testing scope (spec: `docs/superpowers/specs/2026-07-18-review-webapp-design.md`, Testing section).

## File structure

- Modify: `review-app/app/review/page.tsx` — layout, column order, auto-status logic, "Use suggested" button, renamed header.
- Create: `review-app/lib/statusStyles.ts` — extracts `STATUS_LABELS` (moved from the page) and a new `STATUS_COLORS` map (per-status light/dark background + text color pairs) into one small, focused module. Keeps `page.tsx` focused on data/interaction logic rather than growing it further with style constants.

## Auto-status implementation note

The existing `onFrenchChange(id, value)` handler is the single call site for both manual typing and the new "Use suggested" button (the button calls the same handler with `suggestedFrench` as the value), so the auto-status rule is implemented once, inside that handler:

```
if value is non-empty: also patch status to "changed"
if value is empty: also patch status to "not_reviewed"
```

This patch is bundled into the same debounced save as the French text change (one PATCH request, not two), and the same local-state update pattern already used elsewhere in the file (`patchRowLocal`) applies to both fields at once.

## Testing

No automated tests (UI, matches original scope). Manual verification after implementation:
- Status column appears first, shows a colored badge matching its value
- Reviewer French / Notes columns are visibly wider than before
- Typing in Reviewer French auto-switches status to Changed; clearing it back to empty reverts to Not reviewed
- "Use suggested" button populates Reviewer French with the suggested text and triggers the same auto-status switch
- Manually setting status to Approved/Flagged on a row with an empty Reviewer French field persists (isn't overridden)
- Page renders correctly in both light and dark mode
