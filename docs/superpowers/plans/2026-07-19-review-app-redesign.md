# Review App Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt the approved mockup-derived visual redesign of the review page — new status vocabulary (with a DB migration), a full visual system (Inter font, warm background, indigo accent, CSS Grid layout), click-to-copy on Live/Suggested French, and a per-cell "differs" highlight — while preserving all existing autosave/retry/data-fetching behavior unchanged.

**Architecture:** Rename the `RowStatus` enum's stored values (small, idempotent migration), propagate the rename through the small set of files that reference status literals, add the Inter font globally via `next/font/google`, then rewrite `app/review/page.tsx`'s markup/styling to the new CSS Grid-based visual system using CSS custom properties for light/dark-aware design tokens (inline `style` props can't respond to `@media` queries, so anything that needs to differ between light/dark is expressed as a CSS custom property referenced via `var(...)`, not a literal inline color).

**Tech Stack:** Same as the existing app — Next.js 15 (App Router), React 19, TypeScript, `next/font/google` (new: replaces the option of manual `<link>` tags for loading Inter — same visual outcome, but self-hosted/optimized per Next.js convention rather than a runtime request to Google's CDN).

## Global Constraints

- Status values rename: `approved` → `no_changes`, `changed` → `suggestions`. `not_reviewed` and `flagged` are unchanged. Applied via `ALTER TYPE row_status RENAME VALUE`, which preserves existing row data automatically (no data rewrite needed).
- `ExportScope` (`"all" | "changed"` in `lib/csv.ts`, and the `?scope=` query param) is an internal identifier, NOT user-facing copy — it is NOT renamed. Only the `RowStatus` literal comparison inside `selectRowsForExport` changes (`"changed"` → `"suggestions"`).
- Click-to-copy cells (Live French, Suggested French) MUST be real `<button>` elements (keyboard-focusable, Enter/Space-activatable), not `<div onClick>` — this is a deliberate improvement over the mockup's literal markup, to meet this app's existing accessibility floor.
- No new dependencies beyond `next/font/google`, which ships with Next.js itself (not a new package).
- No changes to auth, the seed pipeline, or the rows API's request/response field names — only `status` enum *values* change.
- No automated tests for the new visual layer (UI, matches existing testing scope). `lib/csv.test.ts`'s fixtures are updated because they use the renamed status *values*, not because new UI coverage is being added.
- Design tokens (colors) are expressed as CSS custom properties on `:root`, with a `@media (prefers-color-scheme: dark)` block overriding them — never as literal inline `style` colors for anything that must differ between light and dark, since inline styles cannot respond to media queries.

---

### Task 1: Rename status vocabulary (schema, types, CSV, tests)

**Files:**
- Modify: `review-app/lib/schema.ts`
- Modify: `review-app/lib/rows.ts`
- Modify: `review-app/lib/statusStyles.ts`
- Modify: `review-app/lib/csv.ts`
- Modify: `review-app/lib/csv.test.ts`

**Interfaces:**
- Produces: `RowStatus = "not_reviewed" | "no_changes" | "suggestions" | "flagged"` (was `"approved" | "changed"` for the middle two) — consumed by Task 3's rewritten `app/review/page.tsx`. `suggestedDiffersFromLive(row): boolean` — a **new** pure helper replacing the removed `effectiveFrench`/`differsFromLive` (which become dead code once Task 3 lands, since the new design highlights the Suggested French cell directly rather than the whole row via the reviewer's effective proposal). Consumed by Task 3.

- [ ] **Step 1: Add the rename migration to `review-app/lib/schema.ts`**

Replace the file's contents with:

```ts
// Idempotent: safe to run against a fresh database or one that already has
// the schema applied (e.g. after a redeploy).
export const SCHEMA_STATEMENTS: string[] = [
  `do $$ begin
     create type row_status as enum ('not_reviewed', 'approved', 'changed', 'flagged');
   exception when duplicate_object then null;
   end $$`,
  `create table if not exists rows (
     id text primary key,
     page text not null,
     english text not null,
     live_french text,
     suggested_french text not null,
     reviewer_french text,
     status row_status not null default 'not_reviewed',
     notes text,
     updated_at timestamptz not null default now()
   )`,
  `do $$ begin
     alter type row_status rename value 'approved' to 'no_changes';
   exception when undefined_object then null;
   end $$`,
  `do $$ begin
     alter type row_status rename value 'changed' to 'suggestions';
   exception when undefined_object then null;
   end $$`,
];
```

Note: the enum is still *created* with the old value names, then immediately renamed in the same migration run — this keeps a from-scratch database and the already-deployed production database converging on the same final state via the same script. On production, the `create type` statement no-ops (already exists), and the two `rename value` statements actually take effect. On a brand-new database, all four statements run in order and produce the same final enum. The `exception when undefined_object` guard makes the rename statements safe to re-run indefinitely (a second run finds `'approved'`/`'changed'` no longer exist and no-ops, rather than erroring).

- [ ] **Step 2: Update `review-app/lib/rows.ts`**

Replace the file's contents with:

```ts
import { getSql } from "./db";

export type RowStatus = "not_reviewed" | "no_changes" | "suggestions" | "flagged";

export interface Row {
  id: string;
  page: string;
  english: string;
  liveFrench: string | null;
  suggestedFrench: string;
  reviewerFrench: string | null;
  status: RowStatus;
  notes: string | null;
  updatedAt: string;
}

interface DbRow {
  id: string;
  page: string;
  english: string;
  live_french: string | null;
  suggested_french: string;
  reviewer_french: string | null;
  status: RowStatus;
  notes: string | null;
  updated_at: string;
}

function fromDb(row: DbRow): Row {
  return {
    id: row.id,
    page: row.page,
    english: row.english,
    liveFrench: row.live_french,
    suggestedFrench: row.suggested_french,
    reviewerFrench: row.reviewer_french,
    status: row.status,
    notes: row.notes,
    updatedAt: row.updated_at,
  };
}

const VALID_STATUSES: RowStatus[] = ["not_reviewed", "no_changes", "suggestions", "flagged"];

export function isValidStatus(value: unknown): value is RowStatus {
  return typeof value === "string" && (VALID_STATUSES as string[]).includes(value);
}

/** True when the pipeline's suggested French differs from the live site's
 * current French (and we have a live-site value to compare against at
 * all). Used to highlight the Suggested French cell specifically, not the
 * whole row. */
export function suggestedDiffersFromLive(row: Row): boolean {
  return row.liveFrench !== null && row.suggestedFrench !== row.liveFrench;
}

export async function listRows(): Promise<Row[]> {
  const sql = getSql();
  const result = (await sql(
    `select id, page, english, live_french, suggested_french, reviewer_french,
            status, notes, updated_at
     from rows
     order by page, id`
  )) as unknown as DbRow[];
  return result.map(fromDb);
}

export interface RowPatch {
  reviewerFrench?: string;
  status?: RowStatus;
  notes?: string;
}

export async function updateRow(id: string, patch: RowPatch): Promise<Row | null> {
  const sql = getSql();
  const result = (await sql(
    `update rows set
       reviewer_french = coalesce($2, reviewer_french),
       status = coalesce($3, status),
       notes = coalesce($4, notes),
       updated_at = now()
     where id = $1
     returning id, page, english, live_french, suggested_french, reviewer_french,
               status, notes, updated_at`,
    [id, patch.reviewerFrench ?? null, patch.status ?? null, patch.notes ?? null]
  )) as unknown as DbRow[];
  return result[0] ? fromDb(result[0]) : null;
}
```

Note: `effectiveFrench` and `differsFromLive` are removed — Task 3's redesigned page uses `suggestedDiffersFromLive` instead (a plain comparison of `suggestedFrench` to `liveFrench`, not the "reviewer's effective proposal" comparison the old helpers did). Nothing else in the codebase imports the two removed functions (verified: only `app/review/page.tsx` used them, which Task 3 rewrites).

- [ ] **Step 3: Update `review-app/lib/statusStyles.ts`**

Replace the file's contents with:

```ts
import type { RowStatus } from "./rows";

export const STATUS_LABELS: Record<RowStatus, string> = {
  not_reviewed: "Not reviewed",
  no_changes: "No changes",
  suggestions: "Suggestions",
  flagged: "Flagged",
};

// CSS class names defined in app/review/page.tsx's <style> block.
export const STATUS_BADGE_CLASS: Record<RowStatus, string> = {
  not_reviewed: "status-badge status-badge--not-reviewed",
  no_changes: "status-badge status-badge--no-changes",
  suggestions: "status-badge status-badge--suggestions",
  flagged: "status-badge status-badge--flagged",
};
```

- [ ] **Step 4: Update `review-app/lib/csv.ts`**

Change only the status comparison inside `selectRowsForExport` (leave `ExportScope`'s own `"changed"` string alone — see Global Constraints):

```ts
export function selectRowsForExport(rows: Row[], scope: ExportScope): Row[] {
  if (scope === "all") return rows;
  return rows.filter((row) => row.status === "suggestions" || row.status === "flagged");
}
```

- [ ] **Step 5: Update `review-app/lib/csv.test.ts` fixtures**

Replace the file's contents with:

```ts
import { describe, it, expect } from "vitest";
import { rowsToCsv, selectRowsForExport } from "./csv";
import type { Row } from "./rows";

function makeRow(overrides: Partial<Row>): Row {
  return {
    id: "id-1",
    page: "page-1",
    english: "Hello",
    liveFrench: "Bonjour",
    suggestedFrench: "Salut",
    reviewerFrench: null,
    status: "not_reviewed",
    notes: null,
    updatedAt: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

describe("selectRowsForExport", () => {
  it("returns all rows for scope=all", () => {
    const rows = [makeRow({ status: "not_reviewed" }), makeRow({ id: "id-2", status: "flagged" })];
    expect(selectRowsForExport(rows, "all")).toHaveLength(2);
  });

  it("returns only suggestions/flagged rows for scope=changed", () => {
    const rows = [
      makeRow({ id: "a", status: "not_reviewed" }),
      makeRow({ id: "b", status: "no_changes" }),
      makeRow({ id: "c", status: "suggestions" }),
      makeRow({ id: "d", status: "flagged" }),
    ];
    const result = selectRowsForExport(rows, "changed");
    expect(result.map((r) => r.id)).toEqual(["c", "d"]);
  });
});

describe("rowsToCsv", () => {
  it("writes a header row and one line per selected row", () => {
    const rows = [makeRow({})];
    const csv = rowsToCsv(rows, "all");
    const lines = csv.trim().split("\r\n");
    expect(lines).toHaveLength(2);
    expect(lines[0]).toBe(
      "ID,Page,English,Live French,Suggested French,Reviewer French,Status,Notes"
    );
  });

  it("escapes commas, quotes, and newlines", () => {
    const rows = [makeRow({ notes: 'has "quotes", a comma, and a\nnewline' })];
    const csv = rowsToCsv(rows, "all");
    expect(csv).toContain('"has ""quotes"", a comma, and a\nnewline"');
  });

  it("renders null fields as empty strings", () => {
    const rows = [makeRow({ liveFrench: null, reviewerFrench: null, notes: null })];
    const csv = rowsToCsv(rows, "all");
    const dataLine = csv.trim().split("\r\n")[1];
    const fields = dataLine.split(",");
    expect(fields[3]).toBe(""); // Live French column
    expect(fields[5]).toBe(""); // Reviewer French column
    expect(fields[7]).toBe(""); // Notes column
  });

  it("applies the changed-only filter before writing rows", () => {
    const rows = [makeRow({ id: "a", status: "not_reviewed" }), makeRow({ id: "b", status: "suggestions" })];
    const csv = rowsToCsv(rows, "changed");
    const lines = csv.trim().split("\r\n");
    expect(lines).toHaveLength(2); // header + one changed row
    expect(lines[1]).toContain("id-1".replace("id-1", "b")); // sanity: row b's id present
  });
});
```

- [ ] **Step 6: Run tests and type-check**

```bash
cd review-app && npm test && npx tsc --noEmit
```

Expected: all tests PASS (17/17), no type errors. (`app/review/page.tsx` and `app/api/export/route.ts` still reference the old `RowStatus`/`STATUS_LABELS` shape correctly since their *usage* of these exports is type-compatible — `tsc` will only fail here if a literal old-value string like `"changed"` remains somewhere still expecting to satisfy `RowStatus`, which Step 6 catches before Task 3 touches `page.tsx` at all.)

- [ ] **Step 7: Commit**

```bash
git add review-app/lib/schema.ts review-app/lib/rows.ts review-app/lib/statusStyles.ts \
        review-app/lib/csv.ts review-app/lib/csv.test.ts
git commit -m "feat(review-app): rename status vocabulary (approved/changed -> no_changes/suggestions)"
```

---

### Task 2: Global font and color-scheme

**Files:**
- Modify: `review-app/app/layout.tsx`

**Interfaces:**
- Produces: Inter font applied globally (via `<body>`'s className) and `color-scheme: light dark` declared globally — consumed implicitly by every page, including Task 3's redesigned review page (which no longer needs to declare `color-scheme` itself).

- [ ] **Step 1: Replace `review-app/app/layout.tsx`**

```tsx
import type { ReactNode } from "react";
import { Inter } from "next/font/google";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
});

export const metadata = { title: "OOTW25 Review" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" style={{ colorScheme: "light dark" }}>
      <body className={inter.className}>{children}</body>
    </html>
  );
}
```

- [ ] **Step 2: Verify it compiles and builds**

```bash
cd review-app && npx tsc --noEmit && npm run build
```

Expected: no type errors; build succeeds (confirms `next/font/google`'s Inter fetch/self-host step works — this happens at build time, requiring network access to Google Fonts once, then the font is self-hosted from the build output).

- [ ] **Step 3: Commit**

```bash
git add review-app/app/layout.tsx
git commit -m "feat(review-app): load Inter font and declare color-scheme globally"
```

---

### Task 3: Redesign the review page (CSS Grid, design tokens, click-to-copy, progress bar)

**Files:**
- Modify: `review-app/app/review/page.tsx` (full rewrite)

**Interfaces:**
- Consumes: `RowStatus`, `Row`, `suggestedDiffersFromLive` from `@/lib/rows` (Task 1); `STATUS_LABELS`, `STATUS_BADGE_CLASS` from `@/lib/statusStyles` (Task 1); Inter font + `color-scheme` from the root layout (Task 2).
- Produces: the `/review` page. No other file depends on its internals.

This task folds together the entire visual redesign (CSS Grid layout, design-token color system, progress bar, reordered/widened filter row, page tag pills, click-to-copy Live/Suggested cells replacing the "Use suggested" button, per-cell differs highlight, restyled export buttons) because it all lands in one file and is only meaningfully reviewable as one cohesive page.

- [ ] **Step 1: Replace `review-app/app/review/page.tsx` with the following**

```tsx
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { suggestedDiffersFromLive, type Row, type RowStatus } from "@/lib/rows";
import { STATUS_LABELS, STATUS_BADGE_CLASS } from "@/lib/statusStyles";

type SaveState = "idle" | "saving" | "error";

const AUTOSAVE_DELAY_MS = 600;
const SAVE_RETRIES = 3;
const RETRY_DELAY_MS = 1000;
const ACCENT = "#4f46e5";
const GRID_COLUMNS = "168px 120px 1fr 1fr 1fr 1fr 220px";

const PAGE_STYLES = `
  :root {
    color-scheme: light dark;
    --bg: oklch(97.5% 0.004 90);
    --text: oklch(20% 0.01 260);
    --text-muted: oklch(50% 0.02 260);
    --h1-color: oklch(18% 0.01 260);
    --card-bg: white;
    --card-border: oklch(90% 0.006 90);
    --header-bg: oklch(98% 0.004 90);
    --header-border: oklch(90% 0.006 90);
    --header-label: oklch(52% 0.01 260);
    --row-border: oklch(93% 0.006 90);
    --english-text: oklch(30% 0.01 260);
    --live-text: oklch(45% 0.01 260);
    --suggested-text: oklch(28% 0.01 260);
    --suggested-diff-bg: oklch(96.5% 0.045 80);
    --input-border: oklch(89% 0.006 90);
    --input-text: oklch(25% 0.01 260);
    --input-bg: white;
    --progress-track: oklch(90% 0.006 90);
    --flagged-row-bg: oklch(99% 0.01 25);
    --tag-bg: color-mix(in oklch, ${ACCENT} 14%, white);
    --tag-text: color-mix(in oklch, ${ACCENT} 75%, black);
    --export-outline-bg: white;
    --export-outline-text: oklch(35% 0.01 260);
    --export-outline-border: oklch(88% 0.006 90);
    --hover-bg: oklch(93% 0.02 260 / 60%);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: oklch(18% 0.006 260);
      --text: oklch(92% 0.005 90);
      --text-muted: oklch(65% 0.01 260);
      --h1-color: oklch(95% 0.004 90);
      --card-bg: oklch(22% 0.006 260);
      --card-border: oklch(32% 0.006 260);
      --header-bg: oklch(24% 0.006 260);
      --header-border: oklch(32% 0.006 260);
      --header-label: oklch(65% 0.01 260);
      --row-border: oklch(30% 0.006 260);
      --english-text: oklch(85% 0.005 90);
      --live-text: oklch(65% 0.01 260);
      --suggested-text: oklch(88% 0.005 90);
      --suggested-diff-bg: oklch(35% 0.06 80 / 35%);
      --input-border: oklch(35% 0.006 260);
      --input-text: oklch(90% 0.005 90);
      --input-bg: oklch(22% 0.006 260);
      --progress-track: oklch(32% 0.006 260);
      --flagged-row-bg: oklch(28% 0.03 25 / 40%);
      --tag-bg: color-mix(in oklch, ${ACCENT} 25%, black);
      --tag-text: color-mix(in oklch, ${ACCENT} 60%, white);
      --export-outline-bg: oklch(24% 0.006 260);
      --export-outline-text: oklch(85% 0.005 90);
      --export-outline-border: oklch(35% 0.006 260);
      --hover-bg: oklch(32% 0.02 260 / 60%);
    }
  }
  .review-shell {
    min-height: 100vh;
    background: var(--bg);
    color: var(--text);
    padding: 36px 40px 60px;
    box-sizing: border-box;
  }
  .eyebrow {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
  }
  .eyebrow-icon {
    width: 26px;
    height: 26px;
    border-radius: 7px;
    background: ${ACCENT};
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .eyebrow-icon-dot {
    width: 10px;
    height: 10px;
    border-radius: 2px;
    background: white;
  }
  .eyebrow-label {
    font-size: 12.5px;
    font-weight: 600;
    color: var(--text-muted);
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }
  .page-title {
    font-size: 26px;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.01em;
    color: var(--h1-color);
  }
  .export-btn {
    height: 38px;
    padding: 0 16px;
    border-radius: 9px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
  }
  .export-btn--outline {
    background: var(--export-outline-bg);
    color: var(--export-outline-text);
    border: 1px solid var(--export-outline-border);
  }
  .export-btn--filled {
    background: ${ACCENT};
    color: white;
    border: none;
  }
  .progress-track {
    flex: 1;
    max-width: 340px;
    height: 8px;
    border-radius: 6px;
    background: var(--progress-track);
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    border-radius: 6px;
    background: ${ACCENT};
    transition: width .3s ease;
  }
  .filter-bar {
    position: sticky;
    top: 0;
    z-index: 1;
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 18px;
  }
  .filter-control {
    height: 38px;
    padding: 0 12px;
    border-radius: 9px;
    border: 1px solid var(--input-border);
    background: var(--input-bg);
    font-size: 13.5px;
    font-weight: 500;
    color: var(--input-text);
  }
  select.filter-control { cursor: pointer; }
  input.filter-control { flex: 1; min-width: 220px; max-width: 360px; }
  .table-card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 1px 2px rgba(20,20,40,0.08);
  }
  .table-scroll { overflow-x: auto; }
  .table-grid { min-width: 1180px; }
  .grid-row { display: grid; }
  .grid-header {
    background: var(--header-bg);
    border-bottom: 1px solid var(--header-border);
    position: sticky;
    top: 0;
    z-index: 1;
  }
  .grid-header-cell {
    padding: 13px 16px;
    font-size: 11.5px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--header-label);
  }
  .grid-header-hint {
    font-weight: 500;
    text-transform: none;
    color: var(--text-muted);
  }
  .grid-data-row { border-bottom: 1px solid var(--row-border); }
  .grid-cell { padding: 16px; box-sizing: border-box; }
  .status-badge {
    width: 100%;
    height: 30px;
    padding: 0 8px;
    border-radius: 20px;
    border: none;
    font-size: 11.5px;
    font-weight: 700;
    cursor: pointer;
  }
  .page-tag {
    background: var(--tag-bg);
    color: var(--tag-text);
    padding: 3px 8px;
    border-radius: 6px;
    display: inline-block;
    font-size: 12.5px;
    font-weight: 600;
  }
  .english-cell {
    font-size: 14px;
    line-height: 1.5;
    color: var(--english-text);
  }
  .copy-cell {
    width: 100%;
    height: 100%;
    text-align: left;
    background: transparent;
    border: none;
    font: inherit;
    font-size: 14px;
    line-height: 1.5;
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
  }
  .copy-cell:hover, .copy-cell:focus-visible {
    background: var(--hover-bg);
  }
  .live-cell { color: var(--live-text); }
  .suggested-cell { color: var(--suggested-text); }
  .suggested-cell--diff { background: var(--suggested-diff-bg); }
  .field-textarea {
    width: 100%;
    height: 100%;
    min-height: 56px;
    resize: none;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid var(--input-border);
    background: var(--input-bg);
    font-size: 13.5px;
    line-height: 1.5;
    color: var(--input-text);
    box-sizing: border-box;
  }
  .notes-textarea { min-height: 34px; font-size: 13px; }
  .meta-text { font-size: 0.75rem; color: var(--text-muted); }
  .status-badge--not-reviewed { background: oklch(92% 0.006 90); color: oklch(45% 0.01 260); }
  .status-badge--no-changes { background: oklch(92% 0.07 150); color: oklch(38% 0.1 150); }
  .status-badge--suggestions { background: oklch(93% 0.07 250); color: oklch(42% 0.13 260); }
  .status-badge--flagged { background: oklch(93% 0.06 25); color: oklch(45% 0.14 25); }
  @media (prefers-color-scheme: dark) {
    .status-badge--not-reviewed { background: oklch(35% 0.01 260); color: oklch(85% 0.005 90); }
    .status-badge--no-changes { background: oklch(30% 0.09 150); color: oklch(85% 0.08 150); }
    .status-badge--suggestions { background: oklch(32% 0.1 260); color: oklch(85% 0.09 260); }
    .status-badge--flagged { background: oklch(32% 0.09 25); color: oklch(85% 0.09 25); }
  }
`;

export default function ReviewPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageFilter, setPageFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [saveStates, setSaveStates] = useState<Record<string, SaveState>>({});
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    fetch("/api/rows")
      .then((res) => res.json())
      .then((data: { rows: Row[] }) => {
        setRows(data.rows);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch rows:", err);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    return () => {
      Object.values(timers.current).forEach(clearTimeout);
    };
  }, []);

  const pages = useMemo(() => Array.from(new Set(rows.map((r) => r.page))).sort(), [rows]);

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (pageFilter !== "all" && row.page !== pageFilter) return false;
      if (statusFilter !== "all" && row.status !== statusFilter) return false;
      if (q) {
        const haystack = `${row.english} ${row.liveFrench ?? ""} ${row.suggestedFrench} ${row.reviewerFrench ?? ""} ${row.notes ?? ""}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [rows, pageFilter, statusFilter, search]);

  const reviewedCount = rows.filter((r) => r.status !== "not_reviewed").length;
  const reviewedPercent = rows.length === 0 ? 0 : Math.round((reviewedCount / rows.length) * 100);

  function patchRowLocal(id: string, patch: Partial<Row>) {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  async function saveRow(id: string, patch: Record<string, unknown>, stateKey?: string) {
    const key = stateKey ?? id;
    setSaveStates((s) => ({ ...s, [key]: "saving" }));
    const attempt = async (retriesLeft: number): Promise<void> => {
      try {
        const res = await fetch(`/api/rows/${encodeURIComponent(id)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        });
        if (!res.ok) throw new Error(`status ${res.status}`);
        setSaveStates((s) => ({ ...s, [key]: "idle" }));
      } catch {
        if (retriesLeft > 0) {
          await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
          return attempt(retriesLeft - 1);
        }
        setSaveStates((s) => ({ ...s, [key]: "error" }));
      }
    };
    await attempt(SAVE_RETRIES);
  }

  function debouncedSave(key: string, id: string, patch: Record<string, unknown>, stateKey?: string) {
    if (timers.current[key]) clearTimeout(timers.current[key]);
    timers.current[key] = setTimeout(() => saveRow(id, patch, stateKey), AUTOSAVE_DELAY_MS);
  }

  // Auto-status rule: a non-empty Reviewer French field always means status
  // "suggestions" (even overriding a manual "flagged"); an emptied field
  // reverts to "not_reviewed". This is the single call site for typing and
  // for the Live/Suggested click-to-copy cells, so the rule applies
  // identically everywhere the field's content can change.
  function onFrenchChange(id: string, value: string) {
    const autoStatus: RowStatus = value.trim() === "" ? "not_reviewed" : "suggestions";
    patchRowLocal(id, { reviewerFrench: value, status: autoStatus });
    debouncedSave(
      `${id}:french`,
      id,
      { reviewerFrench: value, status: autoStatus },
      `${id}:french`
    );
  }

  function onNotesChange(id: string, value: string) {
    patchRowLocal(id, { notes: value });
    debouncedSave(`${id}:notes`, id, { notes: value }, `${id}:notes`);
  }

  function onStatusChange(id: string, status: RowStatus) {
    patchRowLocal(id, { status });
    saveRow(id, { status }, `${id}:status`);
  }

  if (loading) return <p style={{ padding: "1rem" }}>Loading…</p>;

  return (
    <div className="review-shell">
      <style>{PAGE_STYLES}</style>
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 24,
          marginBottom: 28,
        }}
      >
        <div>
          <div className="eyebrow">
            <div className="eyebrow-icon">
              <div className="eyebrow-icon-dot" />
            </div>
            <span className="eyebrow-label">OOTW25 · Translation Review</span>
          </div>
          <h1 className="page-title">OOTW25 — Révision de la traduction (fr-CA)</h1>
        </div>
        <div style={{ display: "flex", gap: 10, flexShrink: 0 }}>
          <a className="export-btn export-btn--outline" href="/api/export?scope=changed">
            Export changed (CSV)
          </a>
          <a className="export-btn export-btn--filled" href="/api/export?scope=all">
            Export all (CSV)
          </a>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 26 }}>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${reviewedPercent}%` }} />
        </div>
        <span className="meta-text" style={{ fontWeight: 600 }}>
          {reviewedCount} / {rows.length} reviewed
        </span>
      </div>

      <div className="filter-bar">
        <select
          className="filter-control"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="all">All statuses</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          className="filter-control"
          value={pageFilter}
          onChange={(e) => setPageFilter(e.target.value)}
        >
          <option value="all">All pages</option>
          {pages.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <input
          className="filter-control"
          type="search"
          placeholder="Search English, French, notes…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="table-card">
        <div className="table-scroll">
          <div className="table-grid">
            <div className="grid-row grid-header" style={{ gridTemplateColumns: GRID_COLUMNS }}>
              <div className="grid-header-cell">Status</div>
              <div className="grid-header-cell">Page</div>
              <div className="grid-header-cell">English</div>
              <div className="grid-header-cell">
                Live French <span className="grid-header-hint">(click to copy)</span>
              </div>
              <div className="grid-header-cell">
                Suggested French <span className="grid-header-hint">(click to copy)</span>
              </div>
              <div className="grid-header-cell">Reviewer French</div>
              <div className="grid-header-cell">Notes</div>
            </div>

            {filteredRows.map((row) => {
              const diff = suggestedDiffersFromLive(row);
              const frenchSaveState = saveStates[`${row.id}:french`] ?? "idle";
              const notesSaveState = saveStates[`${row.id}:notes`] ?? "idle";
              const statusSaveState = saveStates[`${row.id}:status`] ?? "idle";
              return (
                <div
                  key={row.id}
                  className="grid-row grid-data-row"
                  style={{
                    gridTemplateColumns: GRID_COLUMNS,
                    background: row.status === "flagged" ? "var(--flagged-row-bg)" : undefined,
                  }}
                >
                  <div className="grid-cell">
                    <select
                      className={STATUS_BADGE_CLASS[row.status]}
                      value={row.status}
                      onChange={(e) => onStatusChange(row.id, e.target.value as RowStatus)}
                    >
                      {Object.entries(STATUS_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                    {statusSaveState === "saving" && <div className="meta-text">saving…</div>}
                    {statusSaveState === "error" && (
                      <div className="meta-text" style={{ color: "crimson" }}>
                        save failed — edit again to retry
                      </div>
                    )}
                  </div>
                  <div className="grid-cell">
                    <span className="page-tag">{row.page}</span>
                  </div>
                  <div className="grid-cell english-cell">{row.english}</div>
                  <div className="grid-cell">
                    {row.liveFrench ? (
                      <button
                        type="button"
                        className="copy-cell live-cell"
                        title="Click to copy into Reviewer French"
                        onClick={() => onFrenchChange(row.id, row.liveFrench as string)}
                      >
                        {row.liveFrench}
                      </button>
                    ) : (
                      <span className="live-cell">—</span>
                    )}
                  </div>
                  <div className={`grid-cell${diff ? " suggested-cell--diff" : ""}`}>
                    <button
                      type="button"
                      className="copy-cell suggested-cell"
                      title="Click to copy into Reviewer French"
                      onClick={() => onFrenchChange(row.id, row.suggestedFrench)}
                    >
                      {row.suggestedFrench}
                    </button>
                  </div>
                  <div className="grid-cell">
                    <textarea
                      className="field-textarea"
                      value={row.reviewerFrench ?? ""}
                      onChange={(e) => onFrenchChange(row.id, e.target.value)}
                      placeholder="Write reviewer French…"
                    />
                    {frenchSaveState === "saving" && <div className="meta-text">saving…</div>}
                    {frenchSaveState === "error" && (
                      <div className="meta-text" style={{ color: "crimson" }}>
                        save failed — edit again to retry
                      </div>
                    )}
                  </div>
                  <div className="grid-cell">
                    <textarea
                      className="field-textarea notes-textarea"
                      value={row.notes ?? ""}
                      onChange={(e) => onNotesChange(row.id, e.target.value)}
                      placeholder="Add a note"
                    />
                    {notesSaveState === "saving" && <div className="meta-text">saving…</div>}
                    {notesSaveState === "error" && (
                      <div className="meta-text" style={{ color: "crimson" }}>
                        save failed — edit again to retry
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {filteredRows.length === 0 && (
              <div
                style={{
                  padding: "60px 20px",
                  textAlign: "center",
                  color: "var(--text-muted)",
                  fontSize: 14,
                }}
              >
                No rows match your filters.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
```

Note on `<a className="export-btn ...">`: these are plain navigational links to a `GET` endpoint that triggers a file download via `Content-Disposition: attachment` (set in `app/api/export/route.ts`, unchanged) — an `<a href>` is correct here, not a `<button>`; unlike the click-to-copy cells, there is no accessibility gap since native links are already keyboard-focusable and Enter-activatable.

- [ ] **Step 2: Verify it compiles**

```bash
cd review-app && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Run the migration against the real database**

The status-rename migration from Task 1 needs to actually run against the deployed Neon database (it hasn't been applied yet — Task 1 only changed the migration script's source, not the live schema). With `review-app/.env.local` containing the real `DATABASE_URL` (already present from the original deployment setup):

```bash
cd review-app && npm run migrate
```

Expected: `applied 4 schema statement(s)`.

- [ ] **Step 4: Manual verification**

```bash
cd review-app && npm run dev
```

Open `http://localhost:3000`, sign in, and confirm:
- Page renders with Inter font, warm background, indigo accent color, in both light and dark mode (toggle your OS/browser color scheme or use browser devtools emulation)
- Progress bar fills proportionally to reviewed count
- Filter row order is Status, Page, Search; searching matches text in Notes and Live French too (previously it didn't)
- Page names render as colored pill tags
- Clicking the Live French or Suggested French cell text copies it into Reviewer French and sets status to "Suggestions" (via keyboard: Tab to the cell, press Enter or Space — confirms the accessibility requirement)
- The Suggested French cell shows an amber tint specifically (not the whole row) when it differs from Live French
- A row with status "Flagged" shows a subtle background tint
- All 4 status pills (Not reviewed / No changes / Suggestions / Flagged) render with distinct, readable colors in both light and dark mode
- Clearing Reviewer French back to empty reverts status to "Not reviewed"
- Manually selecting "No changes" or "Flagged" from the status dropdown on a row with empty Reviewer French persists after reload
- Autosave indicators (saving…/error) still work for French, Notes, and Status independently
- Both CSV export links still work; the "changed" scope export still returns exactly the rows with status Suggestions or Flagged after the rename
- **Revert any test edits** made during this check back to their original values before finishing, since this runs against the real production database

- [ ] **Step 5: Commit**

```bash
git add review-app/app/review/page.tsx
git commit -m "feat(review-app): redesign review page (CSS Grid, design tokens, click-to-copy)"
```
