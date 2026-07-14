"""Build live-fr.json: a read-only sidecar mapping catalog id -> current
live-site French string, for display in the review artifact as reference
material. This NEVER writes to catalog/*.json and must have zero influence
on the translation pipeline -- it only reads the en/ and fr-live/ snapshots
and the existing catalogs to figure out which live string corresponds to
which catalog id.
"""
import difflib
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from scripts.common import norm, walk, node_en
from scripts.pages import PAGES

_TAG_RE = re.compile(r"<[^>]+>")


def plain_text(s: str) -> str:
    """Tags stripped, whitespace collapsed -- no HTML escaping (this is
    stored as plain JSON text, escaping happens at artifact-render time)."""
    return norm(_TAG_RE.sub("", s))


def align_nodes(en_nodes, live_nodes):
    """Map en_nodes index -> live_nodes index for positions that line up.

    If the two node sequences are the same length, they're assumed to be in
    1:1 correspondence (the common case: the live page has the same DOM
    shape as our en/ snapshot). Otherwise, align structurally using
    difflib.SequenceMatcher over the sequence of (kind, tag-name) tuples --
    content-blind, but good enough to recover alignment across a handful of
    inserted/removed nodes -- and keep only the "equal" blocks. Positions
    with no equal-block match are simply absent from the returned mapping.
    """
    if len(en_nodes) == len(live_nodes):
        return {i: i for i in range(len(en_nodes))}
    en_keys = [(n.kind, n.el.name) for n in en_nodes]
    live_keys = [(n.kind, n.el.name) for n in live_nodes]
    sm = difflib.SequenceMatcher(a=en_keys, b=live_keys, autojunk=False)
    mapping = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                mapping[i1 + k] = j1 + k
    return mapping


def _page_nodes(soup):
    """Non-global, non-empty-text nodes in walk order -- exactly the
    population that extract.py turns into a page's non-meta catalog
    entries, in the same order."""
    return [n for n in walk(soup) if not n.is_global and norm(node_en(n))]


def map_page_content(en_html, live_html, non_meta_ids):
    """Returns {catalog_id: live_value} for a page's non-meta entries."""
    en_soup = BeautifulSoup(en_html, "lxml")
    live_soup = BeautifulSoup(live_html, "lxml")
    en_nodes = _page_nodes(en_soup)
    live_nodes = _page_nodes(live_soup)
    if len(en_nodes) != len(non_meta_ids):
        # Shouldn't happen (catalog was built from this same en/ snapshot
        # with this same walk order) -- but don't blow up the whole run.
        print(f"WARNING: en node count ({len(en_nodes)}) != non-meta "
              f"catalog entry count ({len(non_meta_ids)})", file=sys.stderr)
    mapping = align_nodes(en_nodes, live_nodes)
    out = {}
    for i, cat_id in enumerate(non_meta_ids):
        j = mapping.get(i)
        if j is None or j >= len(live_nodes):
            continue
        value = plain_text(node_en(live_nodes[j]))
        if value:
            out[cat_id] = value
    return out


def map_page_meta(slug, live_html):
    """title/description are matched directly (there's exactly one of
    each), no alignment needed."""
    soup = BeautifulSoup(live_html, "lxml")
    out = {}
    if soup.title and norm(soup.title.string or ""):
        out[f"{slug} § meta § title"] = plain_text(soup.title.string)
    md = soup.find("meta", attrs={"name": "description"})
    if md and norm(md.get("content", "")):
        out[f"{slug} § meta § description"] = plain_text(md["content"])
    return out


def map_global(live_index_html, global_entries):
    """Live-fr global (header/footer/nav) nodes, deduped by first
    occurrence the same way extract.py dedups en global nodes, matched
    positionally against catalog/_global.json. If the deduped live global
    node count doesn't match the catalog's global entry count, we bail out
    entirely (no per-node heuristic for chrome -- it's small and repeats
    identically on every page, so a length mismatch means something
    structural changed and position-guessing would be misleading)."""
    soup = BeautifulSoup(live_index_html, "lxml")
    seen = set()
    deduped = []
    for n in walk(soup):
        if not n.is_global:
            continue
        text = node_en(n)
        if not norm(text):
            continue
        key = norm(text)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(n)
    if len(deduped) != len(global_entries):
        print(f"WARNING: live global node count ({len(deduped)}) != "
              f"_global catalog entry count ({len(global_entries)}); "
              "skipping global live-fr mapping", file=sys.stderr)
        return {}
    out = {}
    for entry, node in zip(global_entries, deduped):
        value = plain_text(node_en(node))
        if value:
            out[entry["id"]] = value
    return out


def main():
    result = {}
    global_path = Path("catalog/_global.json")
    global_entries = (json.loads(global_path.read_text(encoding="utf-8"))
                       if global_path.exists() else [])
    live_index_path = Path("fr-live/index.html")
    if global_entries and live_index_path.exists():
        result.update(map_global(
            live_index_path.read_text(encoding="utf-8"), global_entries))

    coverages = {}
    for slug in PAGES:
        cat_path = Path(f"catalog/{slug}.json")
        if not cat_path.exists():
            continue
        entries = json.loads(cat_path.read_text(encoding="utf-8"))
        ids = [e["id"] for e in entries]

        live_path = Path(f"fr-live/{slug}.html")
        if not live_path.exists():
            print(f"{slug}: no live-fr snapshot, skipping")
            coverages[slug] = 0.0
            continue

        live_html = live_path.read_text(encoding="utf-8")
        en_html = Path(f"en/{slug}.html").read_text(encoding="utf-8")

        page_map = {}
        page_map.update(map_page_meta(slug, live_html))
        non_meta_ids = [e["id"] for e in entries if e["section"] != "meta"]
        page_map.update(map_page_content(en_html, live_html, non_meta_ids))

        result.update(page_map)
        got = sum(1 for i in ids if i in page_map)
        coverage = got / len(ids) if ids else 0.0
        coverages[slug] = coverage
        print(f"{slug}: {got}/{len(ids)} ({coverage:.0%})")

    out_path = Path("live-fr.json")
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")
    print(f"\nwrote {out_path} ({len(result)} entries)")

    low = {s: c for s, c in coverages.items() if c < 0.8}
    if low:
        print("\nPages under 80% coverage:")
        for s, c in sorted(low.items(), key=lambda kv: kv[1]):
            print(f"  {s}: {c:.0%}")
    else:
        print("\nAll pages at or above 80% coverage.")


if __name__ == "__main__":
    sys.exit(main())
