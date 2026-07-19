import type { Row } from "./rows";

const COLUMNS: { key: keyof Row; header: string }[] = [
  { key: "id", header: "ID" },
  { key: "page", header: "Page" },
  { key: "english", header: "English" },
  { key: "liveFrench", header: "Live French" },
  { key: "suggestedFrench", header: "Suggested French" },
  { key: "reviewerFrench", header: "Reviewer French" },
  { key: "status", header: "Status" },
  { key: "notes", header: "Notes" },
];

function escapeCsvField(value: string): string {
  if (/[",\n]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

export type ExportScope = "all" | "changed";

export function selectRowsForExport(rows: Row[], scope: ExportScope): Row[] {
  if (scope === "all") return rows;
  return rows.filter((row) => row.status === "changed" || row.status === "flagged");
}

export function rowsToCsv(rows: Row[], scope: ExportScope): string {
  const selected = selectRowsForExport(rows, scope);
  const lines = [COLUMNS.map((c) => escapeCsvField(c.header)).join(",")];
  for (const row of selected) {
    const line = COLUMNS.map((c) => {
      const value = row[c.key];
      return escapeCsvField(value === null || value === undefined ? "" : String(value));
    }).join(",");
    lines.push(line);
  }
  return lines.join("\r\n") + "\r\n";
}
