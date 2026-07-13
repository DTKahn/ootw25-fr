import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from scripts.common import HEADINGS, node_en, norm, slugify, walk
from scripts.pages import PAGES


def _entry(id_, section, tag, en):
    return {"id": id_, "section": section, "tag": tag, "en": en,
            "fr": "", "status": "pending"}


_ATTR_TAGS = {"placeholder": "placeholder", "value": "button",
              "data-error-msg": "error-msg", "data-unique-msg": "unique-msg"}


def _tag(node):
    if node.kind == "img":
        return "img"
    if node.kind == "attr":
        return _ATTR_TAGS.get(node.attr, node.attr)
    el = node.el
    if el.name == "span":  # elementor-button-text unit
        return "button"
    if el.name == "button" or any(a.name == "button" for a in el.parents):
        return "button"  # submit <button> text (possibly a wrapper div unit)
    return el.name


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
            tag = _tag(node)
            gcount[tag] = gcount.get(tag, 0) + 1
            g = _entry(f"global § chrome § {tag}{gcount[tag]}", "chrome", tag, en)
            new_global.append(g)
            seen_global[key] = g
            continue
        tag = _tag(node)
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
