import { getSql } from "../lib/db";
import { SCHEMA_STATEMENTS } from "../lib/schema";

async function main() {
  const sql = getSql();
  for (const statement of SCHEMA_STATEMENTS) {
    await sql(statement);
  }
  console.log(`applied ${SCHEMA_STATEMENTS.length} schema statement(s)`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
