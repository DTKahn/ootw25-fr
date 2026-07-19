# Review Web App — Design Spec

Date: 2026-07-18
Status: Approved, pending implementation plan

## Purpose

The current review interface is a Claude Artifact (`review.html`), rebuilt from the
`pipeline` branch catalogs and republished by hand whenever it needs to change. It
works for us reviewing the translation ourselves, but it does not work as a tool to
hand off to an external translation reviewer:

- The reviewer needs to work through ~924 strings **across multiple sessions**,
  tracking what they've reviewed and what they're recommending changed.
- Claude Artifacts on this account have no shared/server-side storage capability
  (only `downloads` and `mcp` are available) — a published artifact cannot persist
  a viewer's edits on our behalf. The only artifact-native options are browser
  `localStorage` (single-device, at risk of being cleared) or a save/load file the
  reviewer manages themselves. Neither meets "reliable hosted persistence."
- The reviewer needs to export their recommendations as CSV to send to the web
  team — both a full export and a "changed rows only" export.

This spec covers a small, real web app with a database, built to be extended later
(more reviewers, richer UI, possibly a generalized extraction phase) but scoped
tightly to what's needed now: one reviewer, one project, reliable autosave, CSV
export.

## Non-goals (this iteration)

- Multiple concurrent reviewers on the same row set (single reviewer only; no
  conflict resolution).
- Real user accounts / per-user auth (single shared password is sufficient now).
- Generalizing the extraction/translation pipeline to other sites.
- Editing catalogs directly from the web app (it owns its own copy of the data in
  Postgres; the Python pipeline's catalogs remain the source of truth for the
  *initial* seed only).

## Architecture

A **Next.js** app, deployed to **Vercel**, backed by **Neon Postgres** (via
Vercel's Postgres integration).

- Lives in a new subfolder of this repo (e.g. `review-app/`), deployed
  independently via Vercel's "root directory" project setting. Kept in-repo for
  now since it shares data lineage with the Python pipeline; easy to split into
  its own repo later if it becomes a reusable product across projects.
- **Next.js App Router**: React UI + API routes (`/api/rows`, `/api/rows/[id]`,
  `/api/export`) in a single deployable project.
- **Neon Postgres**: the real source of truth for review state. Every edit writes
  directly to the database — there is no client-side save file and no reliance on
  `localStorage`. This is what actually solves the "don't lose my progress"
  requirement.
- **Auth**: a single shared password (env var) gates the app; a session cookie
  keeps the reviewer logged in. Deliberately minimal — acceptable to leave as-is,
  with the explicit option to upgrade to real per-reviewer auth later if the
  project grows to multiple reviewers.
- **Seeding**: a re-runnable script that reads `catalog/*.json` and the
  `fr-live` snapshot (live-site French comparison data) from this repo and
  **upserts** rows into Postgres by ID. Upsert only touches source-derived
  columns (`english`, `suggested_french`, `live_french`, `page`) — it never
  overwrites a row's reviewer-owned fields (`status`, `reviewer_french`,
  `notes`). This makes it safe to re-run after the catalogs are updated without
  destroying review progress already in the database.

## Data model

Single `rows` table:

| column | type | purpose |
|---|---|---|
| `id` | text, PK | matches the catalog entry ID |
| `page` | text | which site page this string belongs to (grouping/filtering) |
| `english` | text | source text |
| `live_french` | text, nullable | current live-site French, display-only reference |
| `suggested_french` | text | pipeline's proposed translation |
| `reviewer_french` | text, nullable | reviewer's edited translation, if any |
| `status` | enum | `not_reviewed` \| `approved` \| `changed` \| `flagged` |
| `notes` | text, nullable | free-text reviewer notes (e.g. why something is flagged) |
| `updated_at` | timestamp | drives "last saved" UI feedback |

`status` is set explicitly by the reviewer via the UI — it is not purely inferred
from whether `reviewer_french` differs from `suggested_french`, since a row can be
`flagged` (e.g. a source-site defect) without any text edit at all.

## Features

**Review table**
- Grouped/filterable by page and status; free-text search.
- Progress indicator (e.g. "312 / 924 reviewed").
- Columns: page, English, live French (reference, read-only), suggested French
  (reference, read-only), "your French" (editable), status, notes.
- Same visual flag for "proposed differs from live site" carried over from the
  current artifact (blue tint), distinct from the amber used for reviewer edits.

**Inline editing**
- Edits to `reviewer_french` or `notes` autosave (debounced) via
  `PATCH /api/rows/{id}` — no manual save button, since the database is the
  live backing store.
- Status changed via explicit buttons/dropdown per row.

**Export**
- `GET /api/export?scope=all` — every row, current state.
- `GET /api/export?scope=changed` — only rows where `status != not_reviewed`
  (or `reviewer_french` is set / `status == flagged`; see open question below).
- Both generate CSV server-side from current DB state and stream it to the
  browser as a download.

## Error handling

If an autosave `PATCH` fails (network blip), the UI:
- Keeps the reviewer's in-progress text in the input — never overwrites it with a
  stale server response.
- Shows a retry/"unsaved" indicator until the write succeeds.
- Retries automatically a bounded number of times before surfacing a persistent
  error to the reviewer.

Concurrent-edit conflicts are out of scope (single reviewer assumption) — last
write wins.

## Testing

Scoped to where correctness actually matters, not blanket coverage:
- Seed script upsert logic — confirms re-running it never overwrites
  `status` / `reviewer_french` / `notes` on existing rows, and correctly
  inserts new rows / updates source-derived columns.
- CSV export formatting — correct escaping, and correct filtering between
  `all` and `changed` scopes.

## Open questions for implementation planning

- Exact definition of "changed" for the `scope=changed` export: any row with
  `status` in (`changed`, `flagged`), or also including `approved` rows where
  `reviewer_french` differs from `suggested_french`? Needs a decision when
  writing the implementation plan.
- Whether `review.html` (the current artifact) stays available as a fallback/
  secondary view during the transition, or is retired once the web app ships.
