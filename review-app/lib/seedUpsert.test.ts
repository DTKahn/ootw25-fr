import { describe, it, expect } from "vitest";
import { buildUpsertStatement } from "./seedUpsert";
import type { SourceRow } from "./seedSource";

const PROTECTED_COLUMNS = ["status", "reviewer_french", "notes"];

describe("buildUpsertStatement", () => {
  it("returns an empty statement for no rows", () => {
    const result = buildUpsertStatement([]);
    expect(result.text).toBe("");
    expect(result.values).toEqual([]);
  });

  it("builds one values tuple per row with the correct params", () => {
    const rows: SourceRow[] = [
      { id: "a § b § c", page: "a", english: "Hello", liveFrench: "Bonjour", suggestedFrench: "Salut" },
      { id: "d § e § f", page: "d", english: "Bye", liveFrench: null, suggestedFrench: "Au revoir" },
    ];
    const { text, values } = buildUpsertStatement(rows);
    expect(text).toContain("insert into rows");
    expect(text).toContain("on conflict (id) do update set");
    expect(values).toEqual([
      "a § b § c", "a", "Hello", "Bonjour", "Salut",
      "d § e § f", "d", "Bye", null, "Au revoir",
    ]);
  });

  it("never references reviewer-owned columns in the SET clause", () => {
    const rows: SourceRow[] = [
      { id: "x", page: "x", english: "E", liveFrench: null, suggestedFrench: "F" },
    ];
    const { text } = buildUpsertStatement(rows);
    for (const column of PROTECTED_COLUMNS) {
      expect(text).not.toMatch(new RegExp(`\\b${column}\\s*=`));
    }
  });

  it("updates updated_at and all source-derived columns on conflict", () => {
    const rows: SourceRow[] = [
      { id: "x", page: "x", english: "E", liveFrench: null, suggestedFrench: "F" },
    ];
    const { text } = buildUpsertStatement(rows);
    for (const column of ["page", "english", "live_french", "suggested_french", "updated_at"]) {
      expect(text).toMatch(new RegExp(`\\b${column}\\s*=`));
    }
  });
});
