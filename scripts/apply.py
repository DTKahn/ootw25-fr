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


def _set_content(node, fr, soup):
    el = node.el
    if node.kind == "img":
        el["alt"] = fr
    elif node.kind == "attr":
        el[node.attr] = fr
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
            _set_content(node, g["fr"], soup)
        else:
            try:
                e = next(page_entries)
            except StopIteration:
                sys.exit(f"{slug}: page has more nodes than catalog "
                         f"(drift at {en[:80]!r}) — re-run extract")
            if norm(e["en"]) != norm(en):
                sys.exit(f"{slug}: catalog/page drift.\n  catalog: {e['en'][:80]!r}"
                         f"\n  page:    {en[:80]!r}\n  re-run extract")
            _set_content(node, e["fr"], soup)
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
        catalogs.append((slug, json.loads(
            Path(f"catalog/{slug}.json").read_text(encoding="utf-8"))))
    glob = json.loads(Path("catalog/_global.json").read_text(encoding="utf-8"))
    catalogs.append(("_global", glob))
    check_complete(catalogs, identical_ok={norm(s) for s in IDENTICAL_OK})

    global_by_en = {}
    for g in glob:
        global_by_en[g["en"]] = g
        global_by_en[norm(g["en"])] = g
    url_map = build_url_map(PAGES)
    Path("fr").mkdir(exist_ok=True)
    for slug, entries in catalogs[:-1]:
        html = Path(f"en/{slug}.html").read_text(encoding="utf-8")
        out = apply_page(slug, html, entries, global_by_en, url_map)
        name = "index.html" if slug == "index" else f"{slug}.html"
        Path(f"fr/{name}").write_text(out, encoding="utf-8")
        print("wrote", f"fr/{name}")


if __name__ == "__main__":
    main()
