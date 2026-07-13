# OOTW25 French Translation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pipeline that snapshots the 18 English pages of https://ootw25.ca/, extracts every translatable string into per-page JSON catalogs, gets them translated to fr-CA by subagents, and generates both a browsable French mirror and an editable review artifact with a correction loop.

**Architecture:** A shared DOM-walk module (`scripts/common.py`) defines what counts as a translatable node; `extract.py` and `apply.py` both use it so extraction order and application order are identical by construction. The per-page JSON catalogs in `catalog/` are the single source of truth; `fr/` mirror and `review.html` artifact are generated outputs, always regenerable.

**Tech Stack:** Python 3.11+, BeautifulSoup4 + lxml, pytest, curl. No web framework — mirror is static HTML served by `python3 -m http.server`.

## Global Constraints

- The live `/fr/` content on ootw25.ca must NEVER be fetched, read, or referenced — the translation is fresh (spec requirement).
- Target language: Canadian French (fr-CA), formal «vous», Canadian Space Agency / GoC terminology, per `glossary.md`.
- Catalog JSON entry shape (fixed across all tasks): `{"id": str, "section": str, "tag": str, "en": str, "fr": str, "status": "pending"|"translated"|"corrected"}`.
- String ID format: `<slug> § <section-slug> § <tag><n>` (n is 1-based per (section, tag)); `_global` entries use slug `global`; per-page metadata uses section `meta` (e.g. `index § meta § title`).
- `en`/`fr` hold inner HTML (inline tags like `<a>`, `<strong>`, `<em>` preserved verbatim); for `img` entries they hold the `alt` attribute text.
- Tests never hit the network; they run on inline fixtures. Real-site steps use the snapshots in `en/`.
- Snapshots in `en/` are immutable once downloaded — never edited.
- Commit after every task with the trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Repo scaffolding and English snapshots

**Files:**
- Create: `.gitignore`, `requirements.txt`, `scripts/pages.py`, `en/*.html` (18 snapshots)

**Interfaces:**
- Produces: `PAGES: dict[str, str]` in `scripts/pages.py` mapping slug → live URL (slug `index` = homepage). All later tasks import it. Snapshot files named `en/<slug>.html`.

- [ ] **Step 1: Write scaffolding files**

`.gitignore`:
```
.venv/
__pycache__/
.pytest_cache/
```

`requirements.txt`:
```
beautifulsoup4
lxml
pytest
```

`scripts/pages.py`:
```python
PAGES = {
    "index": "https://ootw25.ca/",
    "space-blog": "https://ootw25.ca/space-blog/",
    "ootw25-news": "https://ootw25.ca/ootw25-news/",
    "partners": "https://ootw25.ca/partners/",
    "canada-in-space-storymaps": "https://ootw25.ca/canada-in-space-storymaps/",
    "microhistories": "https://ootw25.ca/microhistories/",
    "educators": "https://ootw25.ca/educators/",
    "students-and-families": "https://ootw25.ca/students-and-families/",
    "artemis-ii-mission": "https://ootw25.ca/artemis-ii-mission/",
    "canadian-space-history": "https://ootw25.ca/canadian-space-history/",
    "contact-us": "https://ootw25.ca/contact-us/",
    "who-are-we": "https://ootw25.ca/who-are-we/",
    "privacy-policy": "https://ootw25.ca/privacy-policy/",
    "ootw25-neil-orford": "https://ootw25.ca/ootw25-neil-orford/",
    "commemorating-col-hadfields-spacewalk": "https://ootw25.ca/commemorating-col-hadfields-spacewalk/",
    "out-of-this-world-25-ootw25-official-press-release": "https://ootw25.ca/out-of-this-world-25-ootw25-official-press-release/",
    "chris-hadfield-from-dreaming-of-space-to-leading-the-iss": "https://ootw25.ca/chris-hadfield-from-dreaming-of-space-to-leading-the-iss/",
    "canadian-history-ehx-biography-chris-hadfield": "https://ootw25.ca/canadian-history-ehx-biography-chris-hadfield/",
}
```

- [ ] **Step 2: Create venv, install deps, make packages importable**

Run: `python3 -m venv .venv && .venv/bin/pip -q install -r requirements.txt && mkdir -p tests && touch scripts/__init__.py tests/__init__.py`
Expected: exit 0. (`scripts` and `tests` must be packages: tests import `scripts.common`, and `tests/test_apply.py` imports the fixture from `tests.test_extract`.)

- [ ] **Step 3: Download the 18 snapshots**

```bash
mkdir -p en && .venv/bin/python -c "
from scripts.pages import PAGES
import subprocess, sys
for slug, url in PAGES.items():
    r = subprocess.run(['curl', '-sSfL', '-o', f'en/{slug}.html', url])
    if r.returncode != 0:
        sys.exit(f'FAILED: {slug} {url}')
    print('ok', slug)
"
```
Expected: 18 `ok` lines, no failure. If any URL fails, STOP and report — no partial snapshots (spec error-handling rule).

- [ ] **Step 4: Verify snapshots are real pages**

Run: `ls en/*.html | wc -l && grep -L '</html>' en/*.html`
Expected: `18` and no filenames listed (every file is complete HTML).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: scaffold repo and snapshot 18 English pages"
```

---

### Task 2: Shared DOM walk + extraction (`common.py`, `extract.py`)

**Files:**
- Create: `scripts/common.py`, `scripts/extract.py`, `tests/test_extract.py`, `catalog/*.json` (generated)

**Interfaces:**
- Consumes: `scripts/pages.py:PAGES`, `en/<slug>.html`.
- Produces:
  - `common.walk(soup) -> list[Node]` where `Node = namedtuple("Node", "el kind is_global")`, `kind` in `{"block", "img"}` — the ONE definition of translatable nodes, in document order.
  - `common.norm(s) -> str` whitespace-collapsed text for matching.
  - `common.node_en(node) -> str` the extractable string for a node (inner HTML or alt).
  - `common.slugify(s) -> str`.
  - `extract.extract_page(slug, html, global_index) -> (page_entries, new_global_entries)` and CLI `python -m scripts.extract` writing `catalog/_global.json` and `catalog/<slug>.json`.

- [ ] **Step 1: Write the failing test**

`tests/test_extract.py`:
```python
from bs4 import BeautifulSoup
from scripts.common import walk, node_en, norm
from scripts.extract import extract_page

FIXTURE = """
<html><head><title>My Page - OOTW25</title>
<meta name="description" content="A test page."></head>
<body>
<header data-elementor-type="header"><nav><ul>
  <li><a href="https://ootw25.ca/educators/">Educators</a></li>
</ul></nav></header>
<h2>The Mission</h2>
<p>First paragraph with <strong>bold</strong> text.</p>
<p>Second paragraph.</p>
<ul><li>A list item.</li></ul>
<a class="elementor-button" href="#"><span class="elementor-button-text">Learn More</span></a>
<img src="x.jpg" alt="An astronaut in space.">
<h2>Partners</h2>
<p>Learn More</p>
<script>var ignored = "yes";</script>
<footer><p>© 2026 OOTW25</p></footer>
</body></html>
"""

def test_walk_finds_translatable_nodes_in_order():
    soup = BeautifulSoup(FIXTURE, "lxml")
    nodes = walk(soup)
    texts = [norm(node_en(n)) for n in nodes]
    assert texts == [
        "Educators",
        "The Mission",
        "First paragraph with <strong>bold</strong> text.",
        "Second paragraph.",
        "A list item.",
        "Learn More",
        "An astronaut in space.",
        "Partners",
        "Learn More",
        "© 2026 OOTW25",
    ]
    assert [n.is_global for n in nodes] == [
        True, False, False, False, False, False, False, False, False, True]

def test_extract_page_ids_sections_and_global_dedup():
    entries, glob = extract_page("my-page", FIXTURE, global_index={})
    ids = [e["id"] for e in entries]
    assert "my-page § meta § title" in ids
    assert "my-page § meta § description" in ids
    assert "my-page § the-mission § p1" in ids
    assert "my-page § the-mission § p2" in ids
    assert "my-page § the-mission § li1" in ids
    assert "my-page § the-mission § button1" in ids
    assert "my-page § the-mission § img1" in ids
    assert "my-page § partners § p1" in ids
    assert [g["id"] for g in glob] == ["global § chrome § a1", "global § chrome § p1"]
    by_id = {e["id"]: e for e in entries}
    assert by_id["my-page § the-mission § p1"]["en"] == \
        "First paragraph with <strong>bold</strong> text."
    assert all(e["fr"] == "" and e["status"] == "pending" for e in entries)
    # second call with populated global_index yields no new global entries
    gi = {norm(g["en"]): g for g in glob}
    _, glob2 = extract_page("my-page", FIXTURE, global_index=gi)
    assert glob2 == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.common'` (add empty `scripts/__init__.py` and `tests/__init__.py` if needed for imports).

- [ ] **Step 3: Implement `scripts/common.py`**

```python
import re
from collections import namedtuple

Node = namedtuple("Node", "el kind is_global")

BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "figcaption"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
SKIP_ANCESTORS = {"script", "style", "noscript", "template"}
GLOBAL_TAGS = {"header", "footer", "nav"}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def slugify(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:40] or "top"


def _is_global(el) -> bool:
    for a in el.parents:
        if a.name in GLOBAL_TAGS or (a.get("data-elementor-type") in ("header", "footer")):
            return True
    return el.name in GLOBAL_TAGS


def _is_button_text(el) -> bool:
    return el.name == "span" and "elementor-button-text" in (el.get("class") or [])


def node_en(node: Node) -> str:
    if node.kind == "img":
        return node.el.get("alt", "").strip()
    return node.el.decode_contents().strip()


def walk(soup) -> list:
    """All translatable nodes in document order. Shared by extract and apply."""
    out = []
    body = soup.body or soup
    for el in body.find_all(True):
        if any(a.name in SKIP_ANCESTORS for a in el.parents):
            continue
        is_block = el.name in BLOCK_TAGS or _is_button_text(el)
        if is_block:
            # innermost blocks only: a <li><p>..</p></li> yields the <p>
            if el.find(list(BLOCK_TAGS)) is not None:
                continue
            # skip blocks that live inside a button span (the span is the unit)
            if any(_is_button_text(a) for a in el.parents):
                continue
            if not norm(el.get_text()):
                continue
            # nav-style <li> wrapping exactly one <a>: the <a> is the unit,
            # so its href survives and only the link text is translated
            unit = el
            if el.name == "li":
                kids = [c for c in el.children
                        if not (isinstance(c, str) and not c.strip())]
                if len(kids) == 1 and getattr(kids[0], "name", None) == "a":
                    unit = kids[0]
            out.append(Node(unit, "block", _is_global(el)))
        elif el.name == "img" and el.get("alt", "").strip():
            out.append(Node(el, "img", _is_global(el)))
    return out
```

- [ ] **Step 4: Implement `scripts/extract.py`**

```python
import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from scripts.common import HEADINGS, node_en, norm, slugify, walk
from scripts.pages import PAGES


def _entry(id_, section, tag, en):
    return {"id": id_, "section": section, "tag": tag, "en": en,
            "fr": "", "status": "pending"}


def extract_page(slug, html, global_index):
    """Returns (page_entries, new_global_entries). global_index maps
    norm(en) -> existing global entry, and is NOT mutated."""
    soup = BeautifulSoup(html, "lxml")
    entries, new_global = [], []
    seen_global = dict(global_index)

    title = soup.title.string if soup.title else None
    if title and norm(title):
        entries.append(_entry(f"{slug} § meta § title", "meta", "title", norm(title)))
    md = soup.find("meta", attrs={"name": "description"})
    if md and norm(md.get("content", "")):
        entries.append(_entry(f"{slug} § meta § description", "meta",
                              "description", norm(md["content"])))

    section, counters, gcount = "top", {}, {}
    for node in walk(soup):
        en = node_en(node)
        if not norm(en):
            continue
        if node.is_global:
            key = norm(en)
            if key in seen_global:
                continue
            tag = ("button" if node.kind == "block" and node.el.name == "span"
                   else "img" if node.kind == "img" else node.el.name)
            gcount[tag] = gcount.get(tag, 0) + 1
            g = _entry(f"global § chrome § {tag}{gcount[tag]}", "chrome", tag, en)
            new_global.append(g)
            seen_global[key] = g
            continue
        tag = ("button" if node.kind == "block" and node.el.name == "span"
               else "img" if node.kind == "img" else node.el.name)
        if node.kind == "block" and node.el.name in HEADINGS:
            section = slugify(en)
            counters = {}
        counters[tag] = counters.get(tag, 0) + 1
        # headings restart the section, so their own id uses the new section
        entries.append(_entry(f"{slug} § {section} § {tag}{counters[tag]}",
                              section, tag, en))
    return entries, new_global


def main():
    Path("catalog").mkdir(exist_ok=True)
    global_entries, global_index = [], {}
    for slug in PAGES:
        html = Path(f"en/{slug}.html").read_text()
        entries, new_global = extract_page(slug, html, global_index)
        for g in new_global:
            global_entries.append(g)
            global_index[norm(g["en"])] = g
        Path(f"catalog/{slug}.json").write_text(
            json.dumps(entries, ensure_ascii=False, indent=2))
        print(f"{slug}: {len(entries)} strings")
    Path("catalog/_global.json").write_text(
        json.dumps(global_entries, ensure_ascii=False, indent=2))
    print(f"_global: {len(global_entries)} strings")


if __name__ == "__main__":
    sys.exit(main())
```

Note for implementer: the fixture test is the contract. If the real Elementor markup makes `walk()` miss text (checked in Step 7), extend `walk()`/`extract_page()` and ADD a fixture case reproducing it — don't special-case real pages outside `common.py`.

- [ ] **Step 5: Run tests until they pass**

Run: `.venv/bin/pytest tests/test_extract.py -v`
Expected: 2 passed. Iterate on `common.py`/`extract.py` (not the test's expected values) until green.

- [ ] **Step 6: Run extraction on real snapshots**

Run: `.venv/bin/python -m scripts.extract`
Expected: one line per page with a plausible string count (home page likely 50–150; no page should be 0), plus `_global`.

- [ ] **Step 7: Coverage heuristic check**

```bash
.venv/bin/python - <<'EOF'
import json, re
from pathlib import Path
from bs4 import BeautifulSoup
from scripts.pages import PAGES

for slug in PAGES:
    soup = BeautifulSoup(Path(f"en/{slug}.html").read_text(), "lxml")
    for t in soup(["script", "style", "noscript", "template"]):
        t.decompose()
    visible = len(re.findall(r"\w+", soup.body.get_text()))
    cat = json.loads(Path(f"catalog/{slug}.json").read_text())
    caught = sum(len(re.findall(r"\w+", re.sub(r"<[^>]+>", "", e["en"]))) for e in cat)
    glob = json.loads(Path("catalog/_global.json").read_text())
    gcaught = sum(len(re.findall(r"\w+", re.sub(r"<[^>]+>", "", e["en"]))) for e in glob)
    pct = 100 * (caught + gcaught) / max(visible, 1)
    flag = "  <-- INVESTIGATE" if pct < 85 else ""
    print(f"{slug}: {pct:.0f}% of {visible} visible words captured{flag}")
EOF
```
Expected: every page ≥ 85%. For any flagged page, diff visible text vs. catalog text, extend `walk()` (with a new fixture test case), re-run Steps 5–7.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat: extract translatable strings into per-page catalogs"
```

---

### Task 3: fr-CA glossary and style guide

**Files:**
- Create: `glossary.md`

**Interfaces:**
- Produces: `glossary.md`, pasted verbatim into every translator subagent prompt (Task 6) and used by the lead for review.

- [ ] **Step 1: Scan catalogs for recurring terms**

```bash
.venv/bin/python - <<'EOF'
import json, re, collections
from pathlib import Path
words = collections.Counter()
for f in Path("catalog").glob("*.json"):
    for e in json.loads(f.read_text()):
        text = re.sub(r"<[^>]+>", "", e["en"])
        for m in re.findall(r"\b[A-Z][A-Za-z0-9&.'-]+(?:\s+[A-Z][A-Za-z0-9&.'-]+)*", text):
            if len(m) > 3:
                words[m] += 1
print(*[f"{c:4d}  {w}" for w, c in words.most_common(60)], sep="\n")
EOF
```
Expected: frequency list of capitalized terms/proper nouns. Use it to complete the glossary table below (add any recurring term not yet listed).

- [ ] **Step 2: Write `glossary.md`**

Starting content (extend with Step 1 findings — every term appearing on 2+ pages must get a row):

```markdown
# OOTW25 — Glossaire et guide de style fr-CA

## Règles de style
- Registre : « vous » lorsque le site s'adresse au lecteur. Ton institutionnel mais accessible.
- Français canadien; terminologie officielle de l'Agence spatiale canadienne et du gouvernement du Canada.
- Guillemets français « … » (avec espaces insécables intérieures); apostrophe typographique (').
- Espace insécable avant « : » et « % »; pas d'espace avant « ; ! ? » (usage canadien/OQLF).
- Majuscules accentuées obligatoires (É, À, Ê…).
- Dates : « le 22 avril 2001 ». Nombres : virgule décimale, espace insécable pour les milliers.
- Fidélité : traduire tout le contenu, sans résumer ni adapter le sens.
- Balises HTML incluses dans les chaînes (`<a>`, `<strong>`, `<em>`) : conserver telles quelles,
  ne traduire que le texte; ne jamais modifier les attributs `href`.

## Termes fixes
| English | Français | Note |
|---|---|---|
| spacewalk | sortie extravéhiculaire | « sortie dans l'espace » interdit |
| Canadian Space Agency (CSA) | Agence spatiale canadienne (ASC) | |
| International Space Station (ISS) | Station spatiale internationale (SSI) | |
| Canadarm2 | Canadarm2 | invariant |
| Artemis II | Artemis II | invariant (usage ASC) |
| Orion spacecraft | vaisseau spatial Orion | |
| Space Launch System (SLS) | Space Launch System (SLS) | invariant |
| mission specialist | spécialiste de mission | |
| astronaut | astronaute | |
| STEAM | STIAM | sciences, technologie, ingénierie, arts, mathématiques |
| Learning Hub | Carrefour d'apprentissage | |
| Students & Families | Élèves et familles | |
| Educators | Éducateurs | |
| Indigenous | autochtone | minuscule sauf « peuples Autochtones » selon contexte GoC : utiliser « Autochtones » (nom), « autochtone » (adjectif) |
| StoryMap(s) | StoryMap(s) | invariant (nom de produit Esri) |
| Out of This World 25 / OOTW25 | Out of This World 25 / OOTW25 | invariant; gloss possible à la première occurrence |
| McMaster Children and Youth University (MCYU) | McMaster Children and Youth University (MCYU) | invariant |
| CanHist.ca | CanHist.ca | invariant |
| Chris Hadfield, Jeremy Hansen, etc. | invariants | noms propres |

## Chaînes identiques autorisées (fr == en)
Noms propres seuls, « Canadarm2 », « OOTW25 », noms de partenaires, adresses courriel, numéros.
```

- [ ] **Step 3: Lead review of glossary**

The lead (main session) reads the completed glossary against the Step 1 term list and confirms every 2+-page term has a row. This is a review gate, not a test.

- [ ] **Step 4: Commit**

```bash
git add glossary.md && git commit -m "feat: add fr-CA glossary and style guide"
```

---

### Task 4: French mirror generator (`apply.py`)

**Files:**
- Create: `scripts/apply.py`, `tests/test_apply.py`, `fr/` (generated later, in Task 7)

**Interfaces:**
- Consumes: `common.walk/node_en/norm`, `catalog/*.json`, `en/*.html`, `PAGES`.
- Produces: `apply.apply_page(slug, html, entries, global_by_en, url_map) -> str` (French HTML) and CLI `python -m scripts.apply` writing `fr/<slug>.html`. `url_map: dict[str, str]` maps live URLs (with and without trailing slash) → `<slug>.html`.

- [ ] **Step 1: Write the failing test**

`tests/test_apply.py`:
```python
import pytest
from scripts.apply import apply_page, build_url_map, check_complete
from scripts.extract import extract_page
from tests.test_extract import FIXTURE


def _translated():
    entries, glob = extract_page("my-page", FIXTURE, global_index={})
    fr = {
        "my-page § meta § title": "Ma page - OOTW25",
        "my-page § meta § description": "Une page de test.",
        "my-page § the-mission § p1":
            "Premier paragraphe avec du texte en <strong>gras</strong>.",
        "my-page § the-mission § p2": "Deuxième paragraphe.",
        "my-page § the-mission § li1": "Un élément de liste.",
        "my-page § the-mission § button1": "En savoir plus",
        "my-page § the-mission § img1": "Un astronaute dans l'espace.",
        "my-page § the-mission § h21": "La mission",
        "my-page § partners § h21": "Partenaires",
        "my-page § partners § p1": "En savoir plus",
        "global § chrome § a1": "Éducateurs",
        "global § chrome § p1": "© 2026 OOTW25",
    }
    for e in entries + glob:
        e["fr"] = fr[e["id"]]
        e["status"] = "translated"
    return entries, glob


def test_apply_replaces_text_sets_lang_rewrites_links():
    entries, glob = _translated()
    url_map = build_url_map({"educators": "https://ootw25.ca/educators/"})
    out = apply_page("my-page", FIXTURE, entries,
                     {e["en"]: e for e in glob}, url_map)
    assert 'lang="fr-CA"' in out
    assert "<title>Ma page - OOTW25</title>" in out
    assert "Deuxième paragraphe." in out
    assert "du texte en <strong>gras</strong>" in out
    assert 'alt="Un astronaute dans l\'espace."' in out
    assert 'href="educators.html"' in out
    assert "First paragraph" not in out and "Second paragraph" not in out
    assert 'var ignored = "yes";' in out  # scripts untouched


def test_refuses_untranslated():
    entries, glob = _translated()
    entries[3]["fr"] = ""
    entries[3]["status"] = "pending"
    with pytest.raises(SystemExit):
        check_complete([("my-page", entries), ("_global", glob)])


def test_identical_whitelisted_string_passes():
    entries, glob = _translated()
    e = next(x for x in entries if x["en"] == "Learn More" and "partners" in x["id"])
    e["fr"] = ""  # not translated, but en text is whitelisted below
    check_complete([("my-page", entries), ("_global", glob)],
                   identical_ok={"Learn More"})
    assert e["fr"] == "Learn More"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_apply.py -v`
Expected: FAIL with `ModuleNotFoundError` / import errors.

- [ ] **Step 3: Implement `scripts/apply.py`**

```python
import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from scripts.common import node_en, norm, walk
from scripts.pages import PAGES

# strings allowed to remain identical to English (proper nouns etc.)
IDENTICAL_OK = {
    "Canadarm2", "OOTW25", "CanHist.ca", "Artemis II",
    "McMaster Children and Youth University (MCYU)",
}


def build_url_map(pages: dict) -> dict:
    m = {}
    for slug, url in pages.items():
        name = "index.html" if slug == "index" else f"{slug}.html"
        m[url] = name
        m[url.rstrip("/")] = name
    return m


def check_complete(catalogs, identical_ok=frozenset()):
    """catalogs: list of (slug, entries). Exits listing untranslated ids.
    Fills fr=en for whitelisted identical strings."""
    missing = []
    for slug, entries in catalogs:
        for e in entries:
            if not e["fr"].strip():
                if norm(e["en"]) in identical_ok:
                    e["fr"] = e["en"]
                else:
                    missing.append(e["id"])
            if e["status"] == "pending" and e["fr"].strip():
                missing.append(e["id"] + "  (fr filled but status=pending)")
    if missing:
        sys.exit("UNTRANSLATED STRINGS:\n" + "\n".join(missing))


def _set_content(el, kind, fr, soup):
    if kind == "img":
        el["alt"] = fr
    else:
        el.clear()
        el.append(BeautifulSoup(fr, "html.parser"))


def apply_page(slug, html, entries, global_by_en, url_map):
    soup = BeautifulSoup(html, "lxml")
    if soup.html:
        soup.html["lang"] = "fr-CA"

    by_id = {e["id"]: e for e in entries}
    t = by_id.get(f"{slug} § meta § title")
    if t and soup.title:
        soup.title.string = t["fr"]
    d = by_id.get(f"{slug} § meta § description")
    md = soup.find("meta", attrs={"name": "description"})
    if d and md:
        md["content"] = d["fr"]

    page_entries = iter([e for e in entries if e["section"] != "meta"])
    for node in walk(soup):
        en = node_en(node)
        if not norm(en):
            continue
        if node.is_global:
            g = global_by_en.get(en) or global_by_en.get(norm(en))
            if g is None:
                sys.exit(f"{slug}: global string not in _global catalog: {en[:80]!r}")
            _set_content(node.el, node.kind, g["fr"], soup)
        else:
            try:
                e = next(page_entries)
            except StopIteration:
                sys.exit(f"{slug}: page has more nodes than catalog "
                         f"(drift at {en[:80]!r}) — re-run extract")
            if norm(e["en"]) != norm(en):
                sys.exit(f"{slug}: catalog/page drift.\n  catalog: {e['en'][:80]!r}"
                         f"\n  page:    {en[:80]!r}\n  re-run extract")
            _set_content(node.el, node.kind, e["fr"], soup)
    leftover = next(page_entries, None)
    if leftover is not None:
        sys.exit(f"{slug}: catalog has unused entry {leftover['id']} — re-run extract")

    for a in soup.find_all("a", href=True):
        if a["href"] in url_map:
            a["href"] = url_map[a["href"]]
    return str(soup)


def main():
    catalogs = []
    for slug in PAGES:
        catalogs.append((slug, json.loads(Path(f"catalog/{slug}.json").read_text())))
    glob = json.loads(Path("catalog/_global.json").read_text())
    catalogs.append(("_global", glob))
    check_complete(catalogs, identical_ok={norm(s) for s in IDENTICAL_OK})

    global_by_en = {}
    for g in glob:
        global_by_en[g["en"]] = g
        global_by_en[norm(g["en"])] = g
    url_map = build_url_map(PAGES)
    Path("fr").mkdir(exist_ok=True)
    for slug, entries in catalogs[:-1]:
        html = Path(f"en/{slug}.html").read_text()
        out = apply_page(slug, html, entries, global_by_en, url_map)
        name = "index.html" if slug == "index" else f"{slug}.html"
        Path(f"fr/{name}").write_text(out)
        print("wrote", f"fr/{name}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests until they pass**

Run: `.venv/bin/pytest tests/ -v`
Expected: all tests pass (extract tests must still pass — `walk` is shared).

- [ ] **Step 5: Verify the guard on real (untranslated) catalogs**

Run: `.venv/bin/python -m scripts.apply; echo "exit=$?"`
Expected: `UNTRANSLATED STRINGS:` listing pending ids, `exit=1`. This proves the mirror cannot be built with English gaps.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: add French mirror generator with completeness guard"
```

---

### Task 5: Review artifact builder + corrections applier

**Files:**
- Create: `scripts/build_artifact.py`, `scripts/apply_corrections.py`, `tests/test_corrections.py`

**Interfaces:**
- Consumes: `catalog/*.json`.
- Produces: `review.html` (self-contained, CSP-safe: zero external requests) via `python -m scripts.build_artifact`; `python -m scripts.apply_corrections corrections.json` updating catalogs in place. Corrections file format: `{"<string id>": "<corrected fr>", ...}`.

- [ ] **Step 1: Write the failing test for corrections**

`tests/test_corrections.py`:
```python
import json
import pytest
from scripts.apply_corrections import apply_corrections


def _cats():
    return {"my-page": [
        {"id": "my-page § s § p1", "section": "s", "tag": "p",
         "en": "Hello", "fr": "Bonjour", "status": "translated"},
        {"id": "my-page § s § p2", "section": "s", "tag": "p",
         "en": "World", "fr": "Monde", "status": "translated"},
    ]}


def test_applies_and_marks_corrected():
    cats = _cats()
    n = apply_corrections(cats, {"my-page § s § p1": "Bonjour à tous"})
    assert n == 1
    assert cats["my-page"][0]["fr"] == "Bonjour à tous"
    assert cats["my-page"][0]["status"] == "corrected"
    assert cats["my-page"][1]["status"] == "translated"


def test_unknown_id_fails_loudly():
    with pytest.raises(SystemExit):
        apply_corrections(_cats(), {"nope § x § p9": "..."})


def test_empty_correction_rejected():
    with pytest.raises(SystemExit):
        apply_corrections(_cats(), {"my-page § s § p1": "  "})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_corrections.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `scripts/apply_corrections.py`**

```python
import json
import sys
from pathlib import Path


def apply_corrections(catalogs: dict, corrections: dict) -> int:
    """catalogs: {slug: entries}. Mutates in place. Returns count applied."""
    index = {e["id"]: e for entries in catalogs.values() for e in entries}
    applied = 0
    for cid, fr in corrections.items():
        e = index.get(cid)
        if e is None:
            sys.exit(f"unknown string id: {cid!r}")
        if not fr.strip():
            sys.exit(f"empty correction for {cid!r} — refusing")
        if e["fr"] != fr:
            e["fr"] = fr
            e["status"] = "corrected"
            applied += 1
    return applied


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python -m scripts.apply_corrections corrections.json")
    corrections = json.loads(Path(sys.argv[1]).read_text())
    catalogs = {}
    for f in sorted(Path("catalog").glob("*.json")):
        catalogs[f.stem] = json.loads(f.read_text())
    n = apply_corrections(catalogs, corrections)
    for slug, entries in catalogs.items():
        Path(f"catalog/{slug}.json").write_text(
            json.dumps(entries, ensure_ascii=False, indent=2))
    print(f"applied {n} corrections across {len(corrections)} submitted")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_corrections.py -v`
Expected: 3 passed.

- [ ] **Step 5: Implement `scripts/build_artifact.py`**

```python
import html
import json
from pathlib import Path

from scripts.pages import PAGES

TEMPLATE = """<title>OOTW25 — Révision de la traduction française</title>
<style>
  body {{ font: 15px/1.5 system-ui, sans-serif; margin: 0 auto; max-width: 1100px;
         padding: 1rem; }}
  h1 {{ font-size: 1.3rem; }}
  details {{ margin: .6rem 0; border: 1px solid #8884; border-radius: 8px; }}
  summary {{ padding: .5rem .8rem; cursor: pointer; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .92em; }}
  th, td {{ border-top: 1px solid #8883; padding: .45rem .6rem;
            vertical-align: top; text-align: left; }}
  td.id {{ font-family: ui-monospace, monospace; font-size: .78em; opacity: .7;
           white-space: nowrap; max-width: 220px; overflow: hidden;
           text-overflow: ellipsis; }}
  td.fr {{ min-width: 280px; }}
  td.fr[contenteditable]:focus {{ outline: 2px solid #4a90d9; }}
  td.fr.dirty {{ background: #fde68a55; }}
  .bar {{ position: sticky; top: 0; padding: .6rem 0; backdrop-filter: blur(6px);
          display: flex; gap: .8rem; align-items: center; }}
  button {{ padding: .45rem .9rem; border-radius: 6px; border: 1px solid #8886;
            cursor: pointer; font-weight: 600; }}
  .status {{ font-size: .8em; opacity: .75; }}
  @media (prefers-color-scheme: dark) {{ td.fr.dirty {{ background: #b4530955; }} }}
</style>
<div class="bar">
  <h1>OOTW25 — Révision de la traduction (fr-CA)</h1>
  <button id="export">Exporter les corrections</button>
  <span class="status" id="count">0 modification</span>
</div>
<p>Modifiez le texte français directement dans les cellules. Les cellules modifiées
sont surlignées. Cliquez « Exporter les corrections », puis collez le résultat
dans la conversation Claude Code.</p>
<div id="tables">{tables}</div>
<script>
  const dirty = {{}};
  document.querySelectorAll("td.fr").forEach(td => {{
    td.dataset.orig = td.textContent;
    td.addEventListener("input", () => {{
      const changed = td.textContent !== td.dataset.orig;
      td.classList.toggle("dirty", changed);
      if (changed) dirty[td.dataset.id] = td.textContent;
      else delete dirty[td.dataset.id];
      const n = Object.keys(dirty).length;
      document.getElementById("count").textContent =
        n + " modification" + (n > 1 ? "s" : "");
    }});
  }});
  document.getElementById("export").addEventListener("click", async () => {{
    const out = JSON.stringify(dirty, null, 1);
    try {{ await navigator.clipboard.writeText(out); alert("Corrections copiées !"); }}
    catch (e) {{ prompt("Copiez ce texte :", out); }}
  }});
</script>"""


def build(catalog_dir="catalog", out_path="review.html"):
    order = ["_global"] + list(PAGES)
    blocks = []
    for slug in order:
        p = Path(catalog_dir) / f"{slug}.json"
        if not p.exists():
            continue
        entries = json.loads(p.read_text())
        rows = []
        for e in entries:
            rows.append(
                "<tr><td class='id' title='{i}'>{i}</td><td>{en}</td>"
                "<td class='fr' contenteditable='plaintext-only' data-id='{i}'>{fr}</td>"
                "<td class='status'>{st}</td></tr>".format(
                    i=html.escape(e["id"]), en=html.escape(e["en"]),
                    fr=html.escape(e["fr"]), st=e["status"]))
        blocks.append(
            f"<details{' open' if slug == '_global' else ''}>"
            f"<summary>{html.escape(slug)} ({len(entries)})</summary>"
            f"<table><tr><th>ID</th><th>English</th><th>Français (modifiable)</th>"
            f"<th></th></tr>{''.join(rows)}</table></details>")
    Path(out_path).write_text(TEMPLATE.format(tables="".join(blocks)))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    build()
```

- [ ] **Step 6: Smoke-test the artifact builder on real catalogs**

Run: `.venv/bin/python -m scripts.build_artifact && grep -c "contenteditable" review.html`
Expected: `wrote review.html` and a count equal to the total number of catalog entries. Open `review.html` locally in a browser: tables render, editing a French cell highlights it, Export copies JSON.

- [ ] **Step 7: Commit**

```bash
printf 'review.html\ncorrections.json\n' >> .gitignore  # generated / transient
git add -A && git commit -m "feat: add review artifact builder and corrections applier"
```

---

### Task 6: Translation via subagents + lead review

This task is operational (run by the lead in the main session), not code. It fills `fr` for every catalog entry.

**Files:**
- Modify: `catalog/*.json` (fr fields filled, status → `translated`)

**Interfaces:**
- Consumes: `catalog/*.json` from Task 2, `glossary.md` from Task 3.
- Produces: fully translated catalogs that pass `check_complete`.

- [ ] **Step 1: Batch the catalogs**

Group into batches of roughly ≤ 8,000 English words (use the Task 2 Step 7 word counts): `_global` + small pages together; large pages alone. One Sonnet subagent per batch, dispatched in parallel where independent.

- [ ] **Step 2: Dispatch translator subagents**

Prompt template (fill `{files}`, paste full `glossary.md`):

```
You are a professional EN→fr-CA translator for a Canadian educational site about
space history (OOTW25). Translate the catalog files: {files}.

For each file: read the JSON array; for every entry, fill "fr" with the Canadian
French translation of "en" and set "status" to "translated". Rules:
- NEVER modify "id", "section", "tag", or "en". Never add/remove/reorder entries.
- Preserve inline HTML tags exactly (translate only the text inside them);
  never change href or other attributes.
- Entries whose "en" is a pure proper noun (see glossary) get "fr" identical
  to "en", status still "translated".
- Follow this glossary and style guide STRICTLY:
<glossary.md content pasted here in full>
- Faithful translation only: no summarizing, no additions, no tone shifts.
- Do NOT consult ootw25.ca/fr/ or any existing French version of this site.
Write each file back in place (JSON, ensure_ascii=False equivalent — real
accented characters, 2-space indent). Then report: entry count translated per
file, and any entry you were unsure about (list its id and your concern).
```

Dispatch with `subagent_type: "general-purpose"`, `model: "sonnet"`.

- [ ] **Step 3: Mechanical validation after each batch**

```bash
.venv/bin/python - <<'EOF'
import json, re, sys
from pathlib import Path
bad = []
for f in sorted(Path("catalog").glob("*.json")):
    for e in json.loads(f.read_text()):
        if e["status"] == "translated":
            if not e["fr"].strip():
                bad.append((e["id"], "empty fr"))
            if sorted(re.findall(r"</?(\w+)", e["en"])) != \
               sorted(re.findall(r"</?(\w+)", e["fr"])):
                bad.append((e["id"], "inline tag mismatch"))
            for href in re.findall(r'href="[^"]*"', e["en"]):
                if href not in e["fr"]:
                    bad.append((e["id"], f"lost {href}"))
print("\n".join(f"{i}: {r}" for i, r in bad) or "clean")
sys.exit(1 if bad else 0)
EOF
```
Expected: `clean`. Any failure goes back to the translating subagent (via SendMessage) to fix.

- [ ] **Step 4: Lead quality review of each batch**

The lead reads every translated entry (diff-style: `git diff catalog/`) checking: glossary compliance (spot-grep glossary terms, e.g. `grep -l "sortie dans l'espace" catalog/ && echo VIOLATION`), «vous» register, guillemets/typography, fidelity of meaning on a full read of long paragraphs. Reject → send back with specific ids; accept → next step.

- [ ] **Step 5: Cross-page consistency pass**

```bash
.venv/bin/python - <<'EOF'
import json, collections
from pathlib import Path
from scripts.common import norm
by_en = collections.defaultdict(set)
for f in Path("catalog").glob("*.json"):
    for e in json.loads(f.read_text()):
        if e["fr"].strip():
            by_en[norm(e["en"])].add(e["fr"])
for en, frs in sorted(by_en.items()):
    if len(frs) > 1:
        print(f"INCONSISTENT: {en!r} -> {sorted(frs)}")
EOF
```
Expected: no output. Same English string must have one French rendering; fix inconsistencies (pick the better one, update catalogs).

- [ ] **Step 6: Commit**

```bash
git add catalog/ && git commit -m "feat: fr-CA translation of all catalogs (subagent + lead reviewed)"
```

---

### Task 7: Generate mirror + publish review artifact, end-to-end verification

**Files:**
- Create: `fr/*.html` (18 files), `review.html`, `README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: browsable `fr/` mirror; hosted review artifact (Artifact tool, favicon `🇫🇷`, stable file `review.html`).

- [ ] **Step 1: Build the mirror**

Run: `.venv/bin/python -m scripts.apply`
Expected: `wrote fr/...` × 18, exit 0. If the completeness guard fires, return to Task 6.

- [ ] **Step 2: Sentinel verification**

```bash
# English sentinels must be gone from body text; French ones present
.venv/bin/python - <<'EOF'
import re, sys
from pathlib import Path
from bs4 import BeautifulSoup
en_sentinels = ["The Mission", "Learn More", "Who Are We", "first Canadian"]
fail = False
for f in sorted(Path("fr").glob("*.html")):
    soup = BeautifulSoup(f.read_text(), "lxml")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    text = soup.body.get_text(" ")
    hits = [s for s in en_sentinels if s in text]
    if hits:
        print(f"{f.name}: ENGLISH LEFT: {hits}"); fail = True
    if 'lang="fr-CA"' not in f.read_text():
        print(f"{f.name}: lang attr missing"); fail = True
print("clean" if not fail else "", end="")
sys.exit(1 if fail else 0)
EOF
```
Expected: `clean`. (Adjust sentinel list to phrases actually present in `catalog/` English — pick 4–6 frequent ones.)

- [ ] **Step 3: Visual check in browser**

Run: `.venv/bin/python -m http.server 8025 -d fr` (background), then open `http://localhost:8025/index.html` with the Chrome DevTools MCP tools: navigate, screenshot home + 2 subpages, confirm layout intact (CSS/images load from live site), text is French, internal nav links land on local `.html` pages. Kill the server after.

- [ ] **Step 4: Inventory untranslatable embeds (spec: flagged, not translated)**

```bash
.venv/bin/python - <<'EOF'
from pathlib import Path
from bs4 import BeautifulSoup
for f in sorted(Path("en").glob("*.html")):
    soup = BeautifulSoup(f.read_text(), "lxml")
    embeds = [(i.name, (i.get("src") or i.get("href") or "")[:90])
              for i in soup.find_all(["iframe", "embed", "object"])]
    embeds += [("pdf-link", a["href"][:90]) for a in soup.find_all("a", href=True)
               if a["href"].lower().endswith(".pdf")]
    if embeds:
        print(f.stem)
        for kind, src in embeds:
            print(f"  {kind}: {src}")
EOF
```
Expected: a list of iframes (StoryMaps, YouTube) and PDF links per page. Save the output to `docs/external-content.md` with a one-line header explaining these remain English (out of scope per spec) — include this file in the final report to the user.

- [ ] **Step 5: Build and publish the review artifact**

Run: `.venv/bin/python -m scripts.build_artifact`, then publish `review.html` with the Artifact tool (favicon `🇫🇷`, description "Table de révision EN→FR du site OOTW25 — cellules françaises modifiables avec export des corrections"). Give the user the artifact URL and the local mirror command:
`python3 -m http.server 8025 -d fr` → http://localhost:8025/

- [ ] **Step 6: Write `README.md`**

```markdown
# OOTW25 — Traduction française

Fresh fr-CA translation of https://ootw25.ca/ (18 pages). See
`docs/superpowers/specs/2026-07-12-ootw25-french-translation-design.md`.

## Layout
- `en/` — immutable English snapshots
- `catalog/` — string catalogs (source of truth): id / en / fr / status
- `fr/` — generated French mirror (`python -m scripts.apply`)
- `review.html` — generated review table (`python -m scripts.build_artifact`)
- `glossary.md` — fr-CA terminology and style rules

## Preview the French site
python3 -m http.server 8025 -d fr   # then open http://localhost:8025/

## Correction loop
1. Edit French cells in the review artifact → « Exporter les corrections »
2. Paste the JSON into the Claude Code conversation (saved as corrections.json)
3. `python -m scripts.apply_corrections corrections.json`
4. `python -m scripts.apply && python -m scripts.build_artifact` (+ republish artifact)
```

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: generate French mirror and publish review artifact"
```

---

### Task 8: Correction loop (repeat until sign-off)

Operational task, repeated per review round.

- [ ] **Step 1:** Receive corrections (pasted JSON from artifact export, or chat messages citing ids — the lead converts chat corrections into the same `{id: fr}` JSON). Save as `corrections.json`.
- [ ] **Step 2:** Lead reviews corrections against `glossary.md`; if a correction conflicts with a fixed term or would break consistency with the same string elsewhere (re-run Task 6 Step 5 script), flag it to the user with the specific ids instead of silently applying.
- [ ] **Step 3:** Run `.venv/bin/python -m scripts.apply_corrections corrections.json` — expect `applied N corrections`.
- [ ] **Step 4:** Regenerate: `.venv/bin/python -m scripts.apply && .venv/bin/python -m scripts.build_artifact`; re-run Task 7 Step 2 sentinel check; republish the artifact (same file path → same URL).
- [ ] **Step 5:** Commit: `git add -A && git commit -m "fix: apply review corrections round N"`.
- [ ] **Step 6:** Ask the user for the next round or final sign-off.
