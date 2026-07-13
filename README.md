# OOTW25 — Traduction française

Fresh fr-CA translation of https://ootw25.ca/ (18 pages). See
`docs/superpowers/specs/2026-07-12-ootw25-french-translation-design.md`.

## Layout
- `en/` — immutable English snapshots
- `catalog/` — string catalogs (source of truth): id / en / fr / status
- `fr/` — generated French mirror (`.venv/bin/python -m scripts.apply`)
- `review.html` — generated review table (`.venv/bin/python -m scripts.build_artifact`)
- `glossary.md` — fr-CA terminology and style rules
- `docs/external-content.md` — embedded third-party content that remains English

## Preview the French site
```
python3 -m http.server 8025 -d fr   # then open http://localhost:8025/
```

## Correction loop
1. Edit French cells in the review artifact → « Exporter les corrections »
2. Paste the JSON into the Claude Code conversation (saved as corrections.json)
3. `.venv/bin/python -m scripts.apply_corrections corrections.json`
4. `.venv/bin/python -m scripts.apply && .venv/bin/python -m scripts.build_artifact` (+ republish artifact)
