"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { suggestedDiffersFromLive, type Row, type RowStatus } from "@/lib/rows";
import { STATUS_LABELS, STATUS_BADGE_CLASS } from "@/lib/statusStyles";

type SaveState = "idle" | "saving" | "error";

const AUTOSAVE_DELAY_MS = 600;
const SAVE_RETRIES = 3;
const RETRY_DELAY_MS = 1000;
const ACCENT = "#4f46e5";
const GRID_COLUMNS = "168px 160px 1fr 1fr 1fr 1fr 220px";

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
  .id-cell {
    font-family: ui-monospace, monospace;
    font-size: 11.5px;
    color: var(--text-muted);
    overflow-wrap: break-word;
    word-break: break-all;
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
              <div className="grid-header-cell">ID</div>
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
                  <div className="grid-cell id-cell">{row.id}</div>
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
