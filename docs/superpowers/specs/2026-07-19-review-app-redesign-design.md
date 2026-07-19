# Review App Visual Redesign — Design Spec

Date: 2026-07-19
Status: Approved

## Purpose

A design mockup (`Translation Review.dc.html`, exported from a Claude design artifact) proposes a fuller visual redesign of the review page than the prior UI-polish pass covered: a distinct visual system (Inter typeface, warm background, indigo accent color, CSS Grid layout, pill-shaped tags), plus two functional changes (click-to-copy on Live/Suggested French cells, renamed status vocabulary). This spec adopts that direction, reconciled with decisions already made in this project (see below), and grafted onto the app's existing working architecture — the mockup is a **visual and interaction reference only**; the actual data-fetching, autosave/debounce/retry, and API layer are unchanged.

## Decisions (resolved against the mockup)

- **Status vocabulary**: rename the underlying stored values, not just display labels. `approved` → `no_changes`, `changed` → `suggestions`. `not_reviewed` and `flagged` are unchanged. This is a real (small, safe) schema migration — see Data model changes below.
- **Column widths**: adopt the mockup's equal-width columns. English / Live French / Suggested French / Reviewer French are each `1fr` (equal flexible width); Status and Page are fixed-width; Notes is a narrower fixed width. This replaces the prior pass's "Reviewer French/Notes wider" approach.
- **Click-to-copy**: clicking the Live French or Suggested French cell copies its text into Reviewer French (same code path/auto-status behavior as typing). The standalone "Use suggested" button from the prior pass is removed.
- **Differs highlight**: replace the whole-row blue "differs from live" tint with a subtle amber tint on just the Suggested French cell, shown when `suggestedFrench` differs from `liveFrench` (this is a plain text/value comparison — same semantics as the old `differsFromLive`/`effectiveFrench` helpers, just visually scoped to one cell instead of the row).
- **Typeface/background**: adopt Inter (loaded from Google Fonts, one external font request — an accepted tradeoff for visual polish) on a warm off-white background (`oklch(97.5% 0.004 90)`), replacing the current `system-ui` font on plain white.
- **Accent color**: indigo, `#4f46e5`.
- **Layout structure**: replace the `<table>` element with a CSS Grid layout (mirroring the mockup), for cleaner sticky-header and column-width control.
- **Export scope identifier**: the `ExportScope` API/query-param type (`"all" | "changed"`) is an internal implementation detail, not user-facing copy — it is NOT renamed alongside the status vocabulary. `scope=changed` still means "rows with status `suggestions` or `flagged`."

## Adopted from the mockup (uncontroversial, no decision needed)

- Visual progress bar (filled proportionally by `reviewedCount / totalCount`) alongside the existing "X / Y reviewed" text.
- Filter row order: Status filter, then Page filter, then Search — search now matches across English, Live French, Suggested French, Reviewer French, *and* Notes (the current implementation only searches English/Suggested/Reviewer).
- Colored pill-shaped Page tags (accent-tinted background/text) instead of plain text.
- Export buttons: "Export changed (CSV)" (outline style) then "Export all (CSV)" (filled/primary, accent-colored) — this order and treatment matches the mockup and differs from the prior pass's order.
- Rounded status badges/pills, same semantic-color intent as before (gray/blue-ish/green-ish/red-ish) but recolored to the mockup's specific `oklch` palette.

## Explicitly NOT adopted from the mockup (accessibility floor)

The mockup implements click-to-copy as a plain `<div onclick>` with no keyboard affordance. This app already commits to a baseline of keyboard accessibility (visible focus, no mouse-only interactions). Implementation must use a real `<button>` element (unstyled to look like the mockup's clickable cell — full-size, left-aligned text, no visible button chrome except on focus/hover) so the interaction is keyboard-reachable and activatable via Enter/Space, not a raw `onClick` div. This preserves the mockup's visual outcome while meeting the existing quality floor.

Note also that switching from a semantic `<table>` to a CSS Grid of styled `<div>`s loses native screen-reader table semantics. Given this remains a single-reviewer internal tool (auth is already deliberately minimal for the same reason), this tradeoff is accepted, not mitigated with ARIA grid roles, for this pass.

## Data model changes

`review-app/lib/schema.ts`'s `row_status` enum changes from `('not_reviewed', 'approved', 'changed', 'flagged')` to `('not_reviewed', 'no_changes', 'suggestions', 'flagged')`. This is applied as two new idempotent, re-runnable migration statements (Postgres `ALTER TYPE ... RENAME VALUE`, which preserves any existing rows' data — a row previously stored as `'approved'` becomes `'no_changes'` automatically, no data rewrite needed), each wrapped in a `DO` block catching `undefined_object` so re-running `npm run migrate` after the rename doesn't error on an already-renamed value:

```sql
do $$ begin
  alter type row_status rename value 'approved' to 'no_changes';
exception when undefined_object then null;
end $$;

do $$ begin
  alter type row_status rename value 'changed' to 'suggestions';
exception when undefined_object then null;
end $$;
```

Safe to run against the live production database now: all 924 rows currently hold `not_reviewed` (verified after the prior pass's manual-verification cleanup), so there is no meaningful data to migrate, only the enum type definition itself.

## Code changes required by the rename (grep-verified against current code)

- `review-app/lib/rows.ts`: `RowStatus` type and `VALID_STATUSES` array.
- `review-app/lib/statusStyles.ts`: `STATUS_LABELS` and `STATUS_BADGE_CLASS` keys (labels become "No changes" / "Suggestions").
- `review-app/lib/csv.ts`: `selectRowsForExport`'s status check (`"changed"` → `"suggestions"`; `ExportScope`'s own `"changed"` scope-name string is unchanged per the Decisions section above — only the `RowStatus` comparison inside the function changes).
- `review-app/lib/csv.test.ts`: fixture rows using `status: "changed"`/`"approved"` update to `"suggestions"`/`"no_changes"`.
- `review-app/app/review/page.tsx`: the auto-status rule's non-empty branch (`"changed"` → `"suggestions"`).
- `review-app/app/api/export/route.ts`: unaffected — it only reads the `scope` query string, never a `RowStatus` literal.

## Non-goals

- No changes to auth, the seed pipeline's upsert logic, or the rows API's request/response shape (field names stay `reviewerFrench`/`suggestedFrench`/etc. — only the `status` enum's *values* change, not any field name).
- No automated tests for the new visual layer (UI, matches existing testing scope) — `lib/csv.test.ts`'s fixture updates are the one required test change, since it's a status-value rename inside an already-tested pure function, not new UI coverage.
- No ARIA grid semantics (see accessibility note above) — out of scope for this pass.

## Testing

- `lib/csv.test.ts` fixtures updated to use the new status values; existing assertions (escaping, `all`/`changed`-scope filtering) still apply unchanged, just with renamed status strings.
- Manual verification (UI, no automated coverage): progress bar reflects reviewed count; status pills show correct colors for all 4 values in both light and dark mode (this app already supports `prefers-color-scheme` — the mockup itself has no dark-mode consideration, so dark-mode colors for the new palette must be derived, not copied); clicking Live French or Suggested French copies text into Reviewer French and triggers the auto-status rule (now setting `suggestions`, not `changed`); keyboard navigation (Tab + Enter/Space) can trigger the click-to-copy cells; CSV export scope=changed still returns exactly `suggestions`+`flagged` rows after the rename; existing autosave/retry/save-state-indicator behavior from the prior pass is preserved.
