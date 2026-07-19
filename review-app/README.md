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
