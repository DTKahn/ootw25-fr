"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { differsFromLive, type Row, type RowStatus } from "@/lib/rows";
import { STATUS_LABELS, STATUS_BADGE_CLASS } from "@/lib/statusStyles";

type SaveState = "idle" | "saving" | "error";

const AUTOSAVE_DELAY_MS = 600;
const SAVE_RETRIES = 3;
const RETRY_DELAY_MS = 1000;

const PAGE_STYLES = `
  :root {
    color-scheme: light dark;
  }
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
