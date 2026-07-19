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
