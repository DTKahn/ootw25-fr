import type { SourceRow } from "./seedSource";

const SOURCE_COLUMNS = ["id", "page", "english", "live_french", "suggested_french"];

/** Builds a single multi-row upsert. The ON CONFLICT SET clause lists only
 * source-derived columns — status, reviewer_french, and notes are
 * deliberately absent, so re-running the seed can never overwrite a
 * reviewer's work. */
export function buildUpsertStatement(
  rows: SourceRow[]
): { text: string; values: unknown[] } {
  if (rows.length === 0) {
    return { text: "", values: [] };
  }
  const values: unknown[] = [];
  const tuples = rows.map((row, i) => {
    const base = i * SOURCE_COLUMNS.length;
    values.push(row.id, row.page, row.english, row.liveFrench, row.suggestedFrench);
    const placeholders = SOURCE_COLUMNS.map((_, j) => `$${base + j + 1}`);
    return `(${placeholders.join(", ")})`;
  });
  const text = `
    insert into rows (${SOURCE_COLUMNS.join(", ")})
    values ${tuples.join(", ")}
    on conflict (id) do update set
      page = excluded.page,
      english = excluded.english,
      live_french = excluded.live_french,
      suggested_french = excluded.suggested_french,
      updated_at = now()
  `;
  return { text, values };
}
