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
