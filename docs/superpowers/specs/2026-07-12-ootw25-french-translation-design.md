# OOTW25 French Translation — Design

**Date:** 2026-07-12
**Goal:** Produce a fresh, reviewable French (fr-CA) translation of https://ootw25.ca/ — all pages and posts — with a structured EN↔FR review table, a browsable French mirror of the site, and a correction loop. The existing `/fr/` content on the live site is explicitly **not** used as a source or reference.

## Scope

18 URLs from the site's sitemaps:

**Pages (13):** home (`/`), `space-blog`, `ootw25-news`, `partners`, `canada-in-space-storymaps`, `microhistories`, `educators`, `students-and-families`, `artemis-ii-mission`, `canadian-space-history`, `contact-us`, `who-are-we`, `privacy-policy`

**Posts (5):** `ootw25-neil-orford`, `commemorating-col-hadfields-spacewalk`, `out-of-this-world-25-ootw25-official-press-release`, `chris-hadfield-from-dreaming-of-space-to-leading-the-iss`, `canadian-history-ehx-biography-chris-hadfield`

Plus one **`_global`** pseudo-page for shared chrome (nav menu, footer, cookie/banner text) extracted once and translated once.

## Decisions (user-confirmed)

- **Preview form:** local static mirror; publishing to WordPress is out of scope for now.
- **Review format:** interactive hosted artifact with editable French cells.
- **Corrections:** edit in artifact → export → paste back in chat; chat-only corrections also accepted.
- **Style:** Canadian French (fr-CA), formal «vous», Canadian Space Agency / GoC official terminology, French typographic conventions (« » guillemets, espaces insécables, accented capitals).

## Architecture

Single source of truth: a per-page JSON **string catalog**. The review artifact and the French mirror are both generated from it.

```
ootw25-fr/
├── en/<slug>.html          # downloaded English snapshots (verbatim)
├── catalog/<slug>.json     # extracted strings: id, section, en, fr, status
├── fr/<slug>.html          # generated French mirror
├── scripts/
│   ├── extract.py          # en/*.html → catalog/*.json (fr empty)
│   ├── apply.py            # en/*.html + catalog → fr/*.html
│   └── build_artifact.py   # catalog → review artifact HTML
├── glossary.md             # fr-CA term glossary, style rules
└── docs/superpowers/specs/ # this spec, implementation plan
```

### 1. Extraction (`extract.py`, no LLM)

- Parse each snapshot's rendered Elementor HTML.
- Extract, in DOM order: headings, paragraphs, list items, blockquotes, button/link labels, image `alt`, `<title>`, meta description.
- Skip: script/style, hidden elements, URLs, numbers-only strings, strings already extracted into `_global` (nav/footer dedup by exact text match).
- Preserve inline markup (links, `<strong>`, `<em>`) inside a string as HTML so re-injection keeps formatting.
- **String ID:** `<page-slug> § <nearest-preceding-heading, slugified> § <tag><n>`, e.g. `artemis-ii-mission § the-mission § p2`. Stable and human-readable.
- Catalog entry: `{id, section, tag, en, fr: "", status: "pending", selector}` where `selector` is what `apply.py` needs to find the node again (element index path).

### 2. Glossary (`glossary.md`, written before any translation)

Recurring terms with fixed fr-CA renderings (e.g. spacewalk → sortie extravéhiculaire, Canadian Space Agency → Agence spatiale canadienne), proper nouns left untranslated (Canadarm2, Artemis II, StoryMaps, OOTW25, partner names), register («vous»), typography rules. Supplied verbatim to every translator subagent.

### 3. Translation (subagents + lead review)

- Sonnet subagents translate per-page catalog batches: JSON in → same JSON with `fr` filled, IDs and structure untouched, inline HTML preserved, glossary enforced.
- Lead (this session) reviews every batch before accepting: glossary compliance, register, typography, fidelity. Status → `translated`.
- Translation must be faithful — no summarizing, no editorializing.

### 4. French mirror (`apply.py`)

- Copy each English snapshot, replace each catalogued node's content with `fr`.
- Set `<html lang="fr-CA">`, translate `<title>`/meta description.
- Rewrite internal `ootw25.ca` page links to relative local `fr/*.html` links; leave assets (images/CSS/JS) absolute so they load from the live site.
- Fail loudly if a selector no longer matches (catalog/HTML drift).
- User browses via `python3 -m http.server` or opening `fr/index.html`.

### 5. Review artifact (`build_artifact.py`)

- One hosted artifact page: per-page collapsible sections, table rows of {ID, English, editable French cell}.
- Edited cells highlighted; **Export corrections** button copies `{id: corrected-fr}` JSON to clipboard (self-contained, no network — CSP-safe).
- Regenerated (same URL) after each correction round.

### 6. Correction loop

1. User edits French in the artifact (or cites IDs in chat), pastes export back.
2. Lead applies corrections to catalog (`status: corrected`); flags any correction that conflicts with the glossary instead of silently applying inconsistency.
3. Regenerate `fr/` mirror and artifact. Repeat until sign-off.

## Error handling

- Download failures / non-200s: stop and report; no partial silent snapshots.
- Extraction misses (text visible on page but absent from catalog): lead spot-checks each mirror page against its English original; gaps fixed in `extract.py`, catalog regenerated with translations preserved by ID.
- Untranslated strings must be impossible to miss: `apply.py` refuses to run if any `fr` is empty, unless the string is whitelisted as intentionally identical (proper nouns).

## Testing / verification

- `extract.py`: round-trip check — every extracted string must be findable at its selector; word-count of extracted text vs. visible page text as coverage heuristic.
- `apply.py`: after generation, grep mirror for a sample of English-only sentinel phrases (must be absent) and French ones (must be present); verify no leftover `status: pending`.
- Visual: open each mirror page, confirm layout intact and text French.

## Out of scope

- Publishing to WordPress/Polylang (possible follow-up).
- Translating embedded third-party content (ArcGIS StoryMaps content itself, YouTube videos), PDFs/downloadables — flagged in the catalog as `external` for the user's awareness, not translated.
- Ongoing sync with future English content changes.
