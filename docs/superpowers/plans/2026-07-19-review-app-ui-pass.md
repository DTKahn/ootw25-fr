# Review App UI Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the 7 requested UI/UX fixes plus a general cleanup pass to the review app's main page, per the approved design spec.

**Architecture:** Extract status labels/colors into a small new module (`lib/statusStyles.ts`), then rewrite `app/review/page.tsx` to consume it, reorder columns, add the auto-status rule and "Use suggested" button, and apply visual polish via a scoped `<style>` block (badges, card container, sticky filter bar, row hover).

**Tech Stack:** Same as the existing app — Next.js 15 (App Router), React 19, TypeScript. No new dependencies.

## Global Constraints

- No changes to the data model, API routes, auth, seed pipeline, or CSV export — this is a `app/review/page.tsx` (+ new `lib/statusStyles.ts`) scoped UI pass only.
- No new dependencies (no component library, no CSS framework) — continue the existing inline-style / scoped-`<style>`-block approach already used in this codebase.
- No automated tests — this is UI code, verified manually, consistent with the original app's testing scope (spec: `docs/superpowers/specs/2026-07-18-review-webapp-design.md`, Testing section).
- Auto-status rule (spec: `docs/superpowers/specs/2026-07-19-review-app-ui-pass-design.md`, item 6): Reviewer French field non-empty → status becomes `changed` unconditionally (overrides any prior status including `flagged`); Reviewer French field empty → status becomes `not_reviewed`. This fires only on edits to the Reviewer French field itself (typed manually, or via the new "Use suggested" button, which reuses the same code path) — it must NOT fire when the reviewer manually picks a status from the dropdown while the field stays empty.
- Status color palette (light backgrounds / dark text in light mode, muted/translucent backgrounds in dark mode — following the existing `#rrggbb55`-style opacity convention already used in this codebase for dark-mode colors):
  - `not_reviewed` → gray
  - `changed` → blue (same blue already used for the "differs from live" row tint elsewhere in this app)
  - `approved` → green
  - `flagged` → red

---

### Task 1: Extract status labels and badge classes

**Files:**
- Create: `review-app/lib/statusStyles.ts`

**Interfaces:**
- Consumes: `RowStatus` from `./rows`.
- Produces: `STATUS_LABELS: Record<RowStatus, string>`, `STATUS_BADGE_CLASS: Record<RowStatus, string>` — both consumed by `app/review/page.tsx` in Task 2. `STATUS_BADGE_CLASS` values are CSS class name suffixes (`status-badge--<key>`) that Task 2's `<style>` block defines the actual colors for — this task only maps each status to its class name, it does not define any CSS itself.

- [ ] **Step 1: Create `review-app/lib/statusStyles.ts`**

```ts
import type { RowStatus } from "./rows";

export const STATUS_LABELS: Record<RowStatus, string> = {
  not_reviewed: "Not reviewed",
  approved: "Approved",
  changed: "Changed",
  flagged: "Flagged",
};

// CSS class names defined in app/review/page.tsx's <style> block.
export const STATUS_BADGE_CLASS: Record<RowStatus, string> = {
  not_reviewed: "status-badge status-badge--not-reviewed",
  approved: "status-badge status-badge--approved",
  changed: "status-badge status-badge--changed",
  flagged: "status-badge status-badge--flagged",
};
```

- [ ] **Step 2: Verify it compiles**

```bash
cd review-app && npx tsc --noEmit
```

Expected: no errors (the file isn't imported anywhere yet, so this just confirms the syntax/types are valid in isolation).

- [ ] **Step 3: Commit**

```bash
git add review-app/lib/statusStyles.ts
git commit -m "feat(review-app): extract status labels and badge class names"
```

---

### Task 2: Rewrite the review page — column reorder, wider columns, rename, auto-status, "Use suggested" button, visual cleanup

**Files:**
- Modify: `review-app/app/review/page.tsx` (full rewrite)

**Interfaces:**
- Consumes: `STATUS_LABELS`, `STATUS_BADGE_CLASS` from `@/lib/statusStyles` (Task 1); `Row`, `RowStatus`, `differsFromLive` from `@/lib/rows` (unchanged, pre-existing).
- Produces: the `/review` page. No other file depends on its internals.

This task folds together every remaining spec item (column order, widths, rename, auto-status, "Use suggested" button, and the general cleanup pass — card container, sticky filter bar, row hover, type scale, colored status badges) because they all land in the same file and are only meaningfully reviewable together as one page.

- [ ] **Step 1: Replace `review-app/app/review/page.tsx` with the following**

```tsx
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { differsFromLive, type Row, type RowStatus } from "@/lib/rows";
import { STATUS_LABELS, STATUS_BADGE_CLASS } from "@/lib/statusStyles";

type SaveState = "idle" | "saving" | "error";

const AUTOSAVE_DELAY_MS = 600;
const SAVE_RETRIES = 3;
const RETRY_DELAY_MS = 1000;

const PAGE_STYLES = `
  .card {
    border: 1px solid #8883;
    border-radius: 8px;
    overflow-x: auto;
  }
  table.review-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    min-width: 980px;
    font-size: 0.875rem;
  }
  table.review-table th, table.review-table td {
    padding: 0.5rem 0.6rem;
    vertical-align: top;
    text-align: left;
    border-top: 1px solid #8883;
    overflow-wrap: break-word;
  }
  table.review-table th {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    opacity: 0.7;
    border-top: none;
  }
  table.review-table tbody tr:hover {
    background: #00000008;
  }
  .filter-bar {
    position: sticky;
    top: 0;
    z-index: 1;
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
    padding: 0.6rem 0;
    background: canvas;
    backdrop-filter: blur(6px);
  }
  .meta-text {
    font-size: 0.75rem;
    opacity: 0.75;
  }
  .use-suggested-btn {
    font-size: 0.75rem;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    border: 1px solid #8886;
    background: transparent;
    cursor: pointer;
    margin-bottom: 0.3rem;
  }
  .status-badge {
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    white-space: nowrap;
    border: none;
    cursor: pointer;
  }
  .status-badge--not-reviewed { background: #e5e7eb; color: #374151; }
  .status-badge--changed { background: #dbeafe; color: #1d4ed8; }
  .status-badge--approved { background: #dcfce7; color: #15803d; }
  .status-badge--flagged { background: #fee2e2; color: #b91c1c; }
  @media (prefers-color-scheme: dark) {
    table.review-table tbody tr:hover { background: #ffffff10; }
    .status-badge--not-reviewed { background: #37415199; color: #d1d5db; }
    .status-badge--changed { background: #1d4ed855; color: #93c5fd; }
    .status-badge--approved { background: #15803d55; color: #86efac; }
    .status-badge--flagged { background: #b91c1c55; color: #fca5a5; }
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
        const haystack = `${row.english} ${row.suggestedFrench} ${row.reviewerFrench ?? ""}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [rows, pageFilter, statusFilter, search]);

  const reviewedCount = rows.filter((r) => r.status !== "not_reviewed").length;

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
  // "changed" (even overriding a manual "flagged"); an emptied field reverts
  // to "not_reviewed". This is the single call site for both manual typing
  // and the "Use suggested" button, so the rule applies identically to both.
  function onFrenchChange(id: string, value: string) {
    const autoStatus: RowStatus = value.trim() === "" ? "not_reviewed" : "changed";
    patchRowLocal(id, { reviewerFrench: value, status: autoStatus });
    debouncedSave(
      `${id}:french`,
      id,
      { reviewerFrench: value, status: autoStatus },
      `${id}:french`
    );
  }

  function onUseSuggested(id: string, suggestedFrench: string) {
    onFrenchChange(id, suggestedFrench);
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
    <main style={{ fontFamily: "system-ui", padding: "1rem", maxWidth: 1500, margin: "0 auto" }}>
      <style>{PAGE_STYLES}</style>
      <h1 style={{ fontSize: "1.25rem", fontWeight: 600 }}>
        OOTW25 — Révision de la traduction (fr-CA)
      </h1>
      <p className="meta-text">
        {reviewedCount} / {rows.length} reviewed
      </p>
      <div className="filter-bar">
        <select value={pageFilter} onChange={(e) => setPageFilter(e.target.value)}>
          <option value="all">All pages</option>
          {pages.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="all">All statuses</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <input
          type="search"
          placeholder="Search…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <a href="/api/export?scope=all">Export all (CSV)</a>
        <a href="/api/export?scope=changed">Export changed (CSV)</a>
      </div>
      <div className="card">
        <table className="review-table">
          <colgroup>
            <col style={{ width: "8%" }} />
            <col style={{ width: "9%" }} />
            <col style={{ width: "16%" }} />
            <col style={{ width: "14%" }} />
            <col style={{ width: "16%" }} />
            <col style={{ width: "22%" }} />
            <col style={{ width: "15%" }} />
          </colgroup>
          <thead>
            <tr>
              <th>Status</th>
              <th>Page</th>
              <th>English</th>
              <th>Live French</th>
              <th>Suggested French</th>
              <th>Reviewer French</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => {
              const differs = differsFromLive(row);
              const frenchSaveState = saveStates[`${row.id}:french`] ?? "idle";
              const notesSaveState = saveStates[`${row.id}:notes`] ?? "idle";
              const statusSaveState = saveStates[`${row.id}:status`] ?? "idle";
              const hasEdit = (row.reviewerFrench ?? "") !== "";
              return (
                <tr key={row.id} style={{ background: differs ? "#dbeafe66" : undefined }}>
                  <td>
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
                  </td>
                  <td>{row.page}</td>
                  <td>{row.english}</td>
                  <td style={{ opacity: 0.7 }}>{row.liveFrench}</td>
                  <td>{row.suggestedFrench}</td>
                  <td>
                    <button
                      type="button"
                      className="use-suggested-btn"
                      onClick={() => onUseSuggested(row.id, row.suggestedFrench)}
                    >
                      Use suggested
                    </button>
                    <textarea
                      value={row.reviewerFrench ?? ""}
                      onChange={(e) => onFrenchChange(row.id, e.target.value)}
                      rows={2}
                      style={{ width: "100%", background: hasEdit ? "#fde68a55" : undefined }}
                    />
                    {frenchSaveState === "saving" && <div className="meta-text">saving…</div>}
                    {frenchSaveState === "error" && (
                      <div className="meta-text" style={{ color: "crimson" }}>
                        save failed — edit again to retry
                      </div>
                    )}
                  </td>
                  <td>
                    <textarea
                      value={row.notes ?? ""}
                      onChange={(e) => onNotesChange(row.id, e.target.value)}
                      rows={2}
                      style={{ width: "100%" }}
                    />
                    {notesSaveState === "saving" && <div className="meta-text">saving…</div>}
                    {notesSaveState === "error" && (
                      <div className="meta-text" style={{ color: "crimson" }}>
                        save failed — edit again to retry
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </main>
  );
}
```

Note: `background: canvas` in `.filter-bar` is a CSS system color keyword that resolves to the page's actual background in both light and dark mode automatically (no manual dark-mode override needed for it) — this is intentional, not a typo.

- [ ] **Step 2: Verify it compiles**

```bash
cd review-app && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Manual verification**

Run the dev server against the already-seeded database (requires `review-app/.env.local` with a real `DATABASE_URL`, already present from the original deployment setup):

```bash
cd review-app && npm run dev
```

Open `http://localhost:3000`, sign in, and confirm:
- Status is the first column, rendered as a colored pill (gray/blue/green/red for not-reviewed/changed/approved/flagged respectively), correct in both light and dark mode
- Reviewer French and Notes columns are visibly wider than English/Live French/Suggested French
- Header reads "Reviewer French" (not "Your French")
- Typing into Reviewer French auto-switches that row's status pill to "Changed"; clearing the field back to empty reverts it to "Not reviewed"
- Clicking "Use suggested" copies the suggested French text into the Reviewer French box and triggers the same auto-status switch to "Changed"
- Manually picking "Approved" or "Flagged" from the status dropdown on a row with an empty Reviewer French field persists after a page reload (not overridden)
- Row hover highlight, sticky filter bar, and card border render as expected
- **Revert any test edits** made during this check back to their original values (empty Reviewer French / Notes, status back to `not_reviewed`) before finishing, since this runs against the real production database

- [ ] **Step 4: Commit**

```bash
git add review-app/app/review/page.tsx
git commit -m "feat(review-app): status-first colored columns, wider fields, use-suggested button, auto-status rule, visual cleanup"
```
