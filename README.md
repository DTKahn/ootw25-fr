# OOTW25 — Traduction française

Fresh fr-CA translation of https://ootw25.ca/ (18 pages). See
`docs/superpowers/specs/2026-07-12-ootw25-french-translation-design.md`.

## Layout
- `en/` — immutable English snapshots
- `catalog/` — string catalogs (source of truth): id / en / fr / status
- `fr/` — generated French mirror (`.venv/bin/python -m scripts.apply`)
- `review-app/` — hosted web app for reviewer sign-off (see `review-app/README.md`)
- `glossary.md` — fr-CA terminology and style rules
- `docs/external-content.md` — embedded third-party content that remains English

## Preview the French site
```
python3 -m http.server 8025 -d fr   # then open http://localhost:8025/
```

## Review

The translation reviewer works through strings in `review-app/` (deployed to
Vercel, backed by Postgres — see `review-app/README.md`). They export their
recommended changes as CSV directly from that app; there is no longer a
paste-JSON correction loop through this repo.
