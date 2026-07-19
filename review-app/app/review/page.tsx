"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { effectiveFrench, differsFromLive, type Row, type RowStatus } from "@/lib/rows";

const STATUS_LABELS: Record<RowStatus, string> = {
  not_reviewed: "Not reviewed",
  approved: "Approved",
  changed: "Changed",
  flagged: "Flagged",
};

type SaveState = "idle" | "saving" | "error";

const AUTOSAVE_DELAY_MS = 600;
const SAVE_RETRIES = 3;
const RETRY_DELAY_MS = 1000;

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
      });
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

  async function saveRow(id: string, patch: Record<string, unknown>) {
    setSaveStates((s) => ({ ...s, [id]: "saving" }));
    const attempt = async (retriesLeft: number): Promise<void> => {
      try {
        const res = await fetch(`/api/rows/${encodeURIComponent(id)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        });
        if (!res.ok) throw new Error(`status ${res.status}`);
        setSaveStates((s) => ({ ...s, [id]: "idle" }));
      } catch {
        if (retriesLeft > 0) {
          await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
          return attempt(retriesLeft - 1);
        }
        setSaveStates((s) => ({ ...s, [id]: "error" }));
      }
    };
    await attempt(SAVE_RETRIES);
  }

  function debouncedSave(key: string, id: string, patch: Record<string, unknown>) {
    if (timers.current[key]) clearTimeout(timers.current[key]);
    timers.current[key] = setTimeout(() => saveRow(id, patch), AUTOSAVE_DELAY_MS);
  }

  function onFrenchChange(id: string, value: string) {
    patchRowLocal(id, { reviewerFrench: value });
    debouncedSave(id, id, { reviewerFrench: value });
  }

  function onNotesChange(id: string, value: string) {
    patchRowLocal(id, { notes: value });
    debouncedSave(`${id}:notes`, id, { notes: value });
  }

  function onStatusChange(id: string, status: RowStatus) {
    patchRowLocal(id, { status });
    saveRow(id, { status });
  }

  if (loading) return <p style={{ padding: "1rem" }}>Loading…</p>;

  return (
    <main style={{ fontFamily: "system-ui", padding: "1rem", maxWidth: 1400, margin: "0 auto" }}>
      <h1>OOTW25 — Révision de la traduction (fr-CA)</h1>
      <p>
        {reviewedCount} / {rows.length} reviewed
      </p>
      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
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
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9em" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Page</th>
            <th style={{ textAlign: "left" }}>English</th>
            <th style={{ textAlign: "left" }}>Live French</th>
            <th style={{ textAlign: "left" }}>Suggested French</th>
            <th style={{ textAlign: "left" }}>Your French</th>
            <th style={{ textAlign: "left" }}>Status</th>
            <th style={{ textAlign: "left" }}>Notes</th>
          </tr>
        </thead>
        <tbody>
          {filteredRows.map((row) => {
            const differs = differsFromLive(row);
            const saveState = saveStates[row.id] ?? "idle";
            const hasEdit = (row.reviewerFrench ?? "") !== "";
            return (
              <tr
                key={row.id}
                style={{ background: differs ? "#dbeafe66" : undefined, borderTop: "1px solid #8883" }}
              >
                <td style={{ padding: "0.4rem", verticalAlign: "top" }}>{row.page}</td>
                <td style={{ padding: "0.4rem", verticalAlign: "top" }}>{row.english}</td>
                <td style={{ padding: "0.4rem", verticalAlign: "top", opacity: 0.7 }}>
                  {row.liveFrench}
                </td>
                <td style={{ padding: "0.4rem", verticalAlign: "top" }}>{row.suggestedFrench}</td>
                <td style={{ padding: "0.4rem", verticalAlign: "top" }}>
                  <textarea
                    value={row.reviewerFrench ?? ""}
                    onChange={(e) => onFrenchChange(row.id, e.target.value)}
                    rows={2}
                    style={{ width: "100%", background: hasEdit ? "#fde68a55" : undefined }}
                  />
                  {saveState === "saving" && <span> saving…</span>}
                  {saveState === "error" && (
                    <span style={{ color: "crimson" }}> save failed, retrying</span>
                  )}
                </td>
                <td style={{ padding: "0.4rem", verticalAlign: "top" }}>
                  <select
                    value={row.status}
                    onChange={(e) => onStatusChange(row.id, e.target.value as RowStatus)}
                  >
                    {Object.entries(STATUS_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </td>
                <td style={{ padding: "0.4rem", verticalAlign: "top" }}>
                  <textarea
                    value={row.notes ?? ""}
                    onChange={(e) => onNotesChange(row.id, e.target.value)}
                    rows={2}
                    style={{ width: "100%" }}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </main>
  );
}
