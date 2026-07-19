import { getSql } from "./db";

export type RowStatus = "not_reviewed" | "approved" | "changed" | "flagged";

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

const VALID_STATUSES: RowStatus[] = ["not_reviewed", "approved", "changed", "flagged"];

export function isValidStatus(value: unknown): value is RowStatus {
  return typeof value === "string" && (VALID_STATUSES as string[]).includes(value);
}

/** The French text that should currently be treated as "the proposal":
 * the reviewer's edit if they've made one, otherwise the pipeline's
 * suggestion. */
export function effectiveFrench(row: Row): string {
  return row.reviewerFrench && row.reviewerFrench.length > 0
    ? row.reviewerFrench
    : row.suggestedFrench;
}

/** Mirrors the "differs" flag from the old review artifact: true when the
 * current proposal doesn't match the live site's French (and we have a
 * live-site value to compare against at all). */
export function differsFromLive(row: Row): boolean {
  return row.liveFrench !== null && effectiveFrench(row) !== row.liveFrench;
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
