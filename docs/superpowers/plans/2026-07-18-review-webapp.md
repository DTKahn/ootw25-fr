# Review Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Claude Artifact review UI with a small Next.js web app backed by Neon Postgres, so the external translation reviewer gets reliable hosted persistence, inline editing, and CSV export.

**Architecture:** A single Next.js (App Router, TypeScript) project in a new `review-app/` subfolder of this repo, deployed to Vercel. All review state lives in one Postgres `rows` table (Neon). A password-gated session cookie protects the app. A re-runnable Node seed script loads `catalog/*.json` + `live-fr.json` from the repo root and upserts into Postgres without ever touching reviewer-owned columns.

**Tech Stack:** Next.js 15 (App Router), React 19, TypeScript, `@neondatabase/serverless`, Vitest, deployed on Vercel with Neon Postgres.

## Global Constraints

- Single reviewer, single shared password (env var) — no per-user accounts, no conflict resolution (spec: Non-goals).
- Reviewer-owned columns (`status`, `reviewer_french`, `notes`) must never be overwritten by the seed script, even on repeated runs (spec: Architecture — Seeding).
- No client-side save file or `localStorage` reliance — every edit persists to Postgres directly (spec: Architecture — Neon Postgres).
- "Changed" export scope = rows with `status` in (`changed`, `flagged`) (spec: Decisions).
- Autosave must never overwrite in-progress reviewer text with a stale server response, and must retry a bounded number of times before surfacing a persistent error (spec: Error handling).
- Testing is scoped to the seed upsert logic and CSV export formatting/filtering only — not blanket coverage (spec: Testing).
- All new code lives under `review-app/` in this repo; the root Python pipeline (`catalog/`, `scripts/`, etc.) is untouched except where the seed script reads from it and the final README update.

---

### Task 1: Scaffold the Next.js project

**Files:**
- Create: `review-app/package.json`
- Create: `review-app/tsconfig.json`
- Create: `review-app/next.config.mjs`
- Create: `review-app/vitest.config.ts`
- Create: `review-app/.env.example`
- Create: `review-app/.gitignore`
- Create: `review-app/app/layout.tsx`
- Create: `review-app/app/page.tsx`

**Interfaces:**
- Produces: a buildable Next.js app at `review-app/`, npm scripts `dev`, `build`, `start`, `test`, `migrate`, `seed` (the last two implemented in later tasks).

- [ ] **Step 1: Create `review-app/package.json`**

```json
{
  "name": "review-app",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run",
    "migrate": "tsx scripts/migrate.ts",
    "seed": "tsx scripts/seed.ts"
  },
  "dependencies": {
    "@neondatabase/serverless": "^0.10.4",
    "next": "^15.1.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/node": "^22.10.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "tsx": "^4.19.0",
    "typescript": "^5.7.0",
    "vitest": "^2.1.0"
  }
}
```

- [ ] **Step 2: Create `review-app/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create `review-app/next.config.mjs`**

```js
/** @type {import('next').NextConfig} */
const nextConfig = {};
export default nextConfig;
```

- [ ] **Step 4: Create `review-app/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  test: {
    environment: "node",
  },
  resolve: {
    alias: {
      "@": dirname,
    },
  },
});
```

- [ ] **Step 5: Create `review-app/.env.example`**

```
DATABASE_URL=postgres://user:password@host/dbname?sslmode=require
REVIEW_APP_PASSWORD=change-me
AUTH_SECRET=generate-a-long-random-string
```

- [ ] **Step 6: Create `review-app/.gitignore`**

```
node_modules/
.next/
.env.local
```

- [ ] **Step 7: Create `review-app/app/layout.tsx`**

```tsx
import type { ReactNode } from "react";

export const metadata = { title: "OOTW25 Review" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 8: Create `review-app/app/page.tsx`**

```tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/review");
}
```

- [ ] **Step 9: Install dependencies and verify the build**

```bash
cd review-app && npm install
```

```bash
cd review-app && npm run build
```

Expected: build succeeds (it will report that `/review` — created in Task 7 — doesn't exist yet as a route; that's fine, `redirect()` doesn't require the target route to exist at build time, only at request time).

- [ ] **Step 10: Commit**

```bash
git add review-app
git commit -m "feat(review-app): scaffold Next.js project"
```

---

### Task 2: Database schema and Neon client

**Files:**
- Create: `review-app/lib/db.ts`
- Create: `review-app/lib/schema.ts`
- Create: `review-app/scripts/migrate.ts`

**Interfaces:**
- Consumes: `@neondatabase/serverless` (Task 1 dependency).
- Produces: `getSql()` — returns a query function used by every later DB-touching module. `SCHEMA_STATEMENTS: string[]` — the idempotent schema statements, used by `scripts/migrate.ts` and reusable if a test DB is ever needed.

- [ ] **Step 1: Create `review-app/lib/db.ts`**

```ts
import { neon } from "@neondatabase/serverless";

export function getSql() {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL is not set");
  return neon(url);
}
```

- [ ] **Step 2: Create `review-app/lib/schema.ts`**

```ts
// Idempotent: safe to run against a fresh database or one that already has
// the schema applied (e.g. after a redeploy).
export const SCHEMA_STATEMENTS: string[] = [
  `do $$ begin
     create type row_status as enum ('not_reviewed', 'approved', 'changed', 'flagged');
   exception when duplicate_object then null;
   end $$`,
  `create table if not exists rows (
     id text primary key,
     page text not null,
     english text not null,
     live_french text,
     suggested_french text not null,
     reviewer_french text,
     status row_status not null default 'not_reviewed',
     notes text,
     updated_at timestamptz not null default now()
   )`,
];
```

- [ ] **Step 3: Create `review-app/scripts/migrate.ts`**

```ts
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
```

- [ ] **Step 4: Verify it compiles**

```bash
cd review-app && npx tsc --noEmit
```

Expected: no errors. (Running `npm run migrate` requires a real `DATABASE_URL` — deferred to Task 8, where the Neon database is actually provisioned.)

- [ ] **Step 5: Commit**

```bash
git add review-app/lib/db.ts review-app/lib/schema.ts review-app/scripts/migrate.ts
git commit -m "feat(review-app): database schema and Neon client"
```

---

### Task 3: Seed pipeline (source derivation + upsert builder + script)

**Files:**
- Create: `review-app/lib/seedSource.ts`
- Create: `review-app/lib/seedSource.test.ts`
- Create: `review-app/lib/seedUpsert.ts`
- Create: `review-app/lib/seedUpsert.test.ts`
- Create: `review-app/scripts/seed.ts`

**Interfaces:**
- Consumes: `getSql()` from `lib/db.ts` (Task 2).
- Produces: `SourceRow { id, page, english, liveFrench, suggestedFrench }`, `deriveSourceRows(catalogEntries, liveFrench): SourceRow[]`, `plainText(s: string): string`, `buildUpsertStatement(rows: SourceRow[]): { text: string; values: unknown[] }` — all consumed by `scripts/seed.ts` in this task, and `SourceRow`/`plainText` reusable if the seed logic needs extending later.

This task implements the two things the spec explicitly requires tests for on the seeding side: that source text is derived correctly, and that re-running the seed never overwrites reviewer-owned columns.

- [ ] **Step 1: Write the failing tests for source derivation**

Create `review-app/lib/seedSource.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { deriveSourceRows, derivePage, plainText } from "./seedSource";

describe("plainText", () => {
  it("strips HTML tags", () => {
    expect(plainText("Hello <strong>world</strong>")).toBe("Hello world");
  });

  it("decodes HTML entities", () => {
    expect(plainText("Space &amp; Science")).toBe("Space & Science");
  });

  it("collapses whitespace and trims", () => {
    expect(plainText("  Hello\n  world  ")).toBe("Hello world");
  });
});

describe("derivePage", () => {
  it("extracts the page slug before the first ' § '", () => {
    expect(derivePage("artemis-ii-mission § meta § title")).toBe("artemis-ii-mission");
  });

  it("returns the whole id when there is no separator", () => {
    expect(derivePage("no-separator")).toBe("no-separator");
  });
});

describe("deriveSourceRows", () => {
  it("maps catalog entries to source rows, using live French when present", () => {
    const entries = [
      {
        id: "artemis-ii-mission § meta § title",
        section: "meta",
        tag: "title",
        en: "Artemis II Mission &amp; Crew",
        fr: "Mission Artemis II <em>et</em> équipage",
        status: "translated",
      },
    ];
    const liveFrench = {
      "artemis-ii-mission § meta § title": "Mission Artemis II et l'équipage",
    };
    const result = deriveSourceRows(entries, liveFrench);
    expect(result).toEqual([
      {
        id: "artemis-ii-mission § meta § title",
        page: "artemis-ii-mission",
        english: "Artemis II Mission & Crew",
        liveFrench: "Mission Artemis II et l'équipage",
        suggestedFrench: "Mission Artemis II et équipage",
      },
    ]);
  });

  it("sets liveFrench to null when there is no matching key", () => {
    const entries = [
      { id: "x § y § z", section: "y", tag: "z", en: "E", fr: "F", status: "translated" },
    ];
    const result = deriveSourceRows(entries, {});
    expect(result[0].liveFrench).toBeNull();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd review-app && npx vitest run lib/seedSource.test.ts
```

Expected: FAIL — `./seedSource` module not found.

- [ ] **Step 3: Implement `review-app/lib/seedSource.ts`**

```ts
export interface CatalogEntry {
  id: string;
  section: string;
  tag: string;
  en: string;
  fr: string;
  status: string;
}

export interface SourceRow {
  id: string;
  page: string;
  english: string;
  liveFrench: string | null;
  suggestedFrench: string;
}

const TAG_RE = /<[^>]+>/g;
const WS_RE = /\s+/g;
const ENTITY_RE = /&amp;|&lt;|&gt;|&quot;|&#39;/g;
const ENTITIES: Record<string, string> = {
  "&amp;": "&",
  "&lt;": "<",
  "&gt;": ">",
  "&quot;": '"',
  "&#39;": "'",
};

/** Plain-text form of a (possibly markup-bearing) catalog string: tags
 * stripped, entities decoded, whitespace runs collapsed. Mirrors
 * scripts/build_artifact.py's plain() so review-app text matches what the
 * reviewer previously saw in the artifact. */
export function plainText(s: string): string {
  const noTags = s.replace(TAG_RE, "");
  const decoded = noTags.replace(ENTITY_RE, (m) => ENTITIES[m]);
  return decoded.replace(WS_RE, " ").trim();
}

export function derivePage(id: string): string {
  const idx = id.indexOf(" § ");
  return idx === -1 ? id : id.slice(0, idx);
}

export function deriveSourceRows(
  catalogEntries: CatalogEntry[],
  liveFrench: Record<string, string>
): SourceRow[] {
  return catalogEntries.map((entry) => {
    const live = liveFrench[entry.id];
    return {
      id: entry.id,
      page: derivePage(entry.id),
      english: plainText(entry.en),
      liveFrench: live ? plainText(live) : null,
      suggestedFrench: plainText(entry.fr),
    };
  });
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd review-app && npx vitest run lib/seedSource.test.ts
```

Expected: PASS (7 tests).

- [ ] **Step 5: Write the failing tests for the upsert builder**

Create `review-app/lib/seedUpsert.test.ts`:

```ts
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
```

- [ ] **Step 6: Run the tests to verify they fail**

```bash
cd review-app && npx vitest run lib/seedUpsert.test.ts
```

Expected: FAIL — `./seedUpsert` module not found.

- [ ] **Step 7: Implement `review-app/lib/seedUpsert.ts`**

```ts
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
```

- [ ] **Step 8: Run the tests to verify they pass**

```bash
cd review-app && npx vitest run lib/seedUpsert.test.ts
```

Expected: PASS (4 tests).

- [ ] **Step 9: Implement `review-app/scripts/seed.ts`**

```ts
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
```

- [ ] **Step 10: Verify it compiles**

```bash
cd review-app && npx tsc --noEmit
```

Expected: no errors. (Running `npm run seed` against a real database is deferred to Task 8.)

- [ ] **Step 11: Commit**

```bash
git add review-app/lib/seedSource.ts review-app/lib/seedSource.test.ts \
        review-app/lib/seedUpsert.ts review-app/lib/seedUpsert.test.ts \
        review-app/scripts/seed.ts
git commit -m "feat(review-app): seed pipeline with reviewer-safe upsert"
```

---

### Task 4: Auth (password gate + session cookie)

**Files:**
- Create: `review-app/lib/auth.ts`
- Create: `review-app/app/api/auth/route.ts`
- Create: `review-app/app/login/page.tsx`
- Create: `review-app/middleware.ts`

**Interfaces:**
- Produces: `SESSION_COOKIE: string`, `checkPassword(candidate: string): boolean`, `getExpectedSessionValue(): string` — consumed by the auth route and by `middleware.ts`.

Auth here is deliberately minimal (spec: Architecture — Auth): one shared password, one static session-cookie value. No crypto library is needed, and the check works identically in `middleware.ts`'s edge runtime and the Node route handler.

- [ ] **Step 1: Create `review-app/lib/auth.ts`**

```ts
export const SESSION_COOKIE = "session";

export function checkPassword(candidate: string): boolean {
  const expected = process.env.REVIEW_APP_PASSWORD;
  if (!expected) throw new Error("REVIEW_APP_PASSWORD is not set");
  return candidate === expected;
}

// The cookie value is a separate secret from the password itself, so a
// leaked cookie doesn't directly reveal the login password.
export function getExpectedSessionValue(): string {
  const secret = process.env.AUTH_SECRET;
  if (!secret) throw new Error("AUTH_SECRET is not set");
  return secret;
}
```

- [ ] **Step 2: Create `review-app/app/api/auth/route.ts`**

```ts
import { NextRequest, NextResponse } from "next/server";
import { checkPassword, getExpectedSessionValue, SESSION_COOKIE } from "@/lib/auth";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  const password = body?.password;
  if (typeof password !== "string" || !checkPassword(password)) {
    return NextResponse.json({ error: "invalid password" }, { status: 401 });
  }
  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE, getExpectedSessionValue(), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return response;
}
```

- [ ] **Step 3: Create `review-app/app/login/page.tsx`**

```tsx
"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const res = await fetch("/api/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (res.ok) {
      router.push("/review");
    } else {
      setError("Incorrect password");
    }
  }

  return (
    <main style={{ maxWidth: 320, margin: "4rem auto", fontFamily: "system-ui" }}>
      <h1>OOTW25 Review — Sign in</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          autoFocus
          style={{ width: "100%", padding: 8, fontSize: 16 }}
        />
        <button type="submit" style={{ marginTop: 12, padding: "8px 16px" }}>
          Sign in
        </button>
      </form>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
    </main>
  );
}
```

- [ ] **Step 4: Create `review-app/middleware.ts`**

```ts
import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/auth";

export function middleware(request: NextRequest) {
  const session = request.cookies.get(SESSION_COOKIE)?.value;
  const expected = process.env.AUTH_SECRET;
  if (session && expected && session === expected) {
    return NextResponse.next();
  }
  return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
  matcher: ["/review/:path*", "/api/rows/:path*", "/api/export/:path*"],
};
```

- [ ] **Step 5: Verify it compiles**

```bash
cd review-app && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add review-app/lib/auth.ts review-app/app/api/auth review-app/app/login review-app/middleware.ts
git commit -m "feat(review-app): password gate and session cookie"
```

---

### Task 5: Rows data access and API

**Files:**
- Create: `review-app/lib/rows.ts`
- Create: `review-app/app/api/rows/route.ts`
- Create: `review-app/app/api/rows/[id]/route.ts`

**Interfaces:**
- Consumes: `getSql()` from `lib/db.ts` (Task 2).
- Produces: `Row`, `RowStatus`, `isValidStatus(value): value is RowStatus`, `effectiveFrench(row): string`, `differsFromLive(row): boolean`, `listRows(): Promise<Row[]>`, `updateRow(id, patch): Promise<Row | null>` — all consumed by the review page in Task 7, and by CSV export in Task 6.

- [ ] **Step 1: Create `review-app/lib/rows.ts`**

```ts
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
```

Note: `updateRow` uses `coalesce` against `null`, so a patch field is either provided (a string, possibly empty) or omitted — never intentionally set to SQL `NULL`. The review page (Task 7) always sends the current text value, including `""`, so this is never ambiguous in practice.

- [ ] **Step 2: Create `review-app/app/api/rows/route.ts`**

```ts
import { NextResponse } from "next/server";
import { listRows } from "@/lib/rows";

export async function GET() {
  const rows = await listRows();
  return NextResponse.json({ rows });
}
```

- [ ] **Step 3: Create `review-app/app/api/rows/[id]/route.ts`**

```ts
import { NextRequest, NextResponse } from "next/server";
import { updateRow, isValidStatus, type RowPatch } from "@/lib/rows";

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.json().catch(() => null);
  if (!body || typeof body !== "object") {
    return NextResponse.json({ error: "invalid body" }, { status: 400 });
  }

  const patch: RowPatch = {};
  if ("reviewerFrench" in body) {
    if (typeof body.reviewerFrench !== "string") {
      return NextResponse.json({ error: "reviewerFrench must be a string" }, { status: 400 });
    }
    patch.reviewerFrench = body.reviewerFrench;
  }
  if ("notes" in body) {
    if (typeof body.notes !== "string") {
      return NextResponse.json({ error: "notes must be a string" }, { status: 400 });
    }
    patch.notes = body.notes;
  }
  if ("status" in body) {
    if (!isValidStatus(body.status)) {
      return NextResponse.json({ error: "invalid status" }, { status: 400 });
    }
    patch.status = body.status;
  }

  const updated = await updateRow(id, patch);
  if (!updated) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  return NextResponse.json({ row: updated });
}
```

- [ ] **Step 4: Verify it compiles**

```bash
cd review-app && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add review-app/lib/rows.ts review-app/app/api/rows
git commit -m "feat(review-app): rows data access and API routes"
```

---

### Task 6: CSV export

**Files:**
- Create: `review-app/lib/csv.ts`
- Create: `review-app/lib/csv.test.ts`
- Create: `review-app/app/api/export/route.ts`

**Interfaces:**
- Consumes: `Row` from `lib/rows.ts` (Task 5).
- Produces: `ExportScope = "all" | "changed"`, `selectRowsForExport(rows, scope): Row[]`, `rowsToCsv(rows, scope): string` — consumed by the export API route in this task.

- [ ] **Step 1: Write the failing tests**

Create `review-app/lib/csv.test.ts`:

```ts
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

  it("returns only changed/flagged rows for scope=changed", () => {
    const rows = [
      makeRow({ id: "a", status: "not_reviewed" }),
      makeRow({ id: "b", status: "approved" }),
      makeRow({ id: "c", status: "changed" }),
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
    const rows = [makeRow({ id: "a", status: "not_reviewed" }), makeRow({ id: "b", status: "changed" })];
    const csv = rowsToCsv(rows, "changed");
    const lines = csv.trim().split("\r\n");
    expect(lines).toHaveLength(2); // header + one changed row
    expect(lines[1]).toContain("id-1".replace("id-1", "b")); // sanity: row b's id present
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd review-app && npx vitest run lib/csv.test.ts
```

Expected: FAIL — `./csv` module not found.

- [ ] **Step 3: Implement `review-app/lib/csv.ts`**

```ts
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
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd review-app && npx vitest run lib/csv.test.ts
```

Expected: PASS (5 tests).

- [ ] **Step 5: Create `review-app/app/api/export/route.ts`**

```ts
import { NextRequest, NextResponse } from "next/server";
import { listRows } from "@/lib/rows";
import { rowsToCsv, type ExportScope } from "@/lib/csv";

export async function GET(request: NextRequest) {
  const scopeParam = request.nextUrl.searchParams.get("scope");
  const scope: ExportScope = scopeParam === "changed" ? "changed" : "all";
  const rows = await listRows();
  const csv = rowsToCsv(rows, scope);
  return new NextResponse(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="ootw25-review-${scope}.csv"`,
    },
  });
}
```

- [ ] **Step 6: Run the full test suite and verify the build**

```bash
cd review-app && npm test && npx tsc --noEmit
```

Expected: all tests PASS, no type errors.

- [ ] **Step 7: Commit**

```bash
git add review-app/lib/csv.ts review-app/lib/csv.test.ts review-app/app/api/export
git commit -m "feat(review-app): CSV export (all / changed scopes)"
```

---

### Task 7: Review table page

**Files:**
- Create: `review-app/app/review/page.tsx`

**Interfaces:**
- Consumes: `Row`, `RowStatus`, `effectiveFrench`, `differsFromLive` from `lib/rows.ts` (Task 5); `GET /api/rows`, `PATCH /api/rows/{id}` (Task 5); `GET /api/export` (Task 6).
- Produces: the `/review` page — the reviewer's entire working surface. No other task depends on its internals.

No automated tests here (spec: Testing scope is seed + CSV only) — verify manually per Step 3 by running the dev server against a seeded database.

- [ ] **Step 1: Create `review-app/app/review/page.tsx`**

```tsx
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
```

Note: `effectiveFrench` is imported for symmetry with `lib/rows.ts`'s exports but the page itself only needs `differsFromLive`; if a linter flags the unused import, drop it — `differsFromLive` already applies `effectiveFrench` internally.

- [ ] **Step 2: Verify it compiles**

```bash
cd review-app && npx tsc --noEmit
```

Expected: no errors. If `effectiveFrench` is reported unused, remove it from the import list.

- [ ] **Step 3: Manual verification (requires Task 8's provisioned database)**

Once a `DATABASE_URL` is available (Task 8), run:

```bash
cd review-app && npm run migrate && npm run seed && npm run dev
```

Open `http://localhost:3000`, sign in, and confirm: rows load and are grouped/filterable by page and status; search narrows results; editing "Your French" shows the amber highlight and a "saving…" indicator that clears; rows where the proposal differs from live French show the blue tint; changing status persists after a page reload; both CSV export links download a file with the expected rows.

- [ ] **Step 4: Commit**

```bash
git add review-app/app/review
git commit -m "feat(review-app): review table page with inline editing and autosave"
```

---

### Task 8: Deploy and retire the old artifact

**Files:**
- Modify: `README.md` (repo root)
- Create: `review-app/README.md`

**Interfaces:**
- None — this task provisions infrastructure and updates documentation; it doesn't change any code contract.

- [ ] **Step 1: Provision Neon Postgres and Vercel project**

Manual steps (not automatable from this session — requires your accounts):
1. Create a Neon project (or use Vercel's "Storage → Postgres" tab, which provisions Neon under the hood) and copy the pooled connection string.
2. Create a new Vercel project pointing at this GitHub repo (`DTKahn/ootw25-fr`), with **Root Directory** set to `review-app`.
3. In the Vercel project's Environment Variables, set:
   - `DATABASE_URL` — the Neon connection string from step 1.
   - `REVIEW_APP_PASSWORD` — the password you'll give the reviewer.
   - `AUTH_SECRET` — a long random string (e.g. `openssl rand -hex 32`).
4. Deploy.

- [ ] **Step 2: Apply the schema and seed the database**

Locally, with `DATABASE_URL` (and `REVIEW_APP_PASSWORD`/`AUTH_SECRET`, though unused by these two scripts) set to the same values as production, either via `review-app/.env.local` or exported in the shell:

```bash
cd review-app && npm run migrate
cd review-app && npm run seed
```

Expected: `applied 2 schema statement(s)` then `seeded 924 rows`.

- [ ] **Step 3: Create `review-app/README.md`**

```markdown
# OOTW25 Review App

Web app for reviewing the fr-CA translation of https://ootw25.ca/. Replaces
the old `review.html` Claude Artifact — see
`../docs/superpowers/specs/2026-07-18-review-webapp-design.md` for the design
rationale.

## Local development

```
npm install
cp .env.example .env.local   # fill in DATABASE_URL, REVIEW_APP_PASSWORD, AUTH_SECRET
npm run migrate               # applies the schema (idempotent)
npm run seed                  # loads/updates rows from ../catalog + ../live-fr.json
npm run dev
```

## Re-seeding after catalog changes

`npm run seed` is safe to re-run any time the catalogs or live-site snapshot
change — it only touches `page`, `english`, `live_french`, `suggested_french`,
and never overwrites a reviewer's `status`, `reviewer_french`, or `notes`.

## Deployment

Deployed to Vercel with Neon Postgres (`DATABASE_URL`). Root directory:
`review-app`. See the repo root README for environment variable setup.
```

- [ ] **Step 4: Update the repo root `README.md`**

Replace the `review.html` reference and correction-loop section:

```markdown
- `fr/` — generated French mirror (`.venv/bin/python -m scripts.apply`)
- `glossary.md` — fr-CA terminology and style rules
- `docs/external-content.md` — embedded third-party content that remains English
- `review-app/` — hosted web app for reviewer sign-off (see `review-app/README.md`)
```

replacing the previous line that listed `review.html`, and replace the "Correction loop" section with:

```markdown
## Review

The translation reviewer works through strings in `review-app/` (deployed to
Vercel, backed by Postgres — see `review-app/README.md`). They export their
recommended changes as CSV directly from that app; there is no longer a
paste-JSON correction loop through this repo.
```

- [ ] **Step 5: Commit**

```bash
git add README.md review-app/README.md
git commit -m "docs: point review workflow at review-app, retire review.html artifact"
```

- [ ] **Step 6: Push and share the URL**

```bash
git push origin pipeline
```

Then share the deployed Vercel URL and the `REVIEW_APP_PASSWORD` with the reviewer through a separate, non-git channel (e.g. not committed anywhere in this repo).
