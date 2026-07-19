import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { getSql } from "../lib/db";
import { deriveSourceRows, type CatalogEntry } from "../lib/seedSource";
import { buildUpsertStatement } from "../lib/seedUpsert";

// review-app/scripts -> review-app -> repo root
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const CATALOG_DIR = path.join(REPO_ROOT, "catalog");
const LIVE_FR_PATH = path.join(REPO_ROOT, "live-fr.json");

function loadCatalogEntries(): CatalogEntry[] {
  const files = readdirSync(CATALOG_DIR).filter((f) => f.endsWith(".json"));
  const entries: CatalogEntry[] = [];
  for (const file of files) {
    const parsed = JSON.parse(readFileSync(path.join(CATALOG_DIR, file), "utf-8"));
    entries.push(...parsed);
  }
  return entries;
}

function loadLiveFrench(): Record<string, string> {
  try {
    return JSON.parse(readFileSync(LIVE_FR_PATH, "utf-8"));
  } catch {
    return {};
  }
}

async function main() {
  const catalogEntries = loadCatalogEntries();
  const liveFrench = loadLiveFrench();
  const sourceRows = deriveSourceRows(catalogEntries, liveFrench);
  const { text, values } = buildUpsertStatement(sourceRows);
  if (!text) {
    console.log("no rows to seed");
    return;
  }
  const sql = getSql();
  await sql(text, values);
  console.log(`seeded ${sourceRows.length} rows`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
