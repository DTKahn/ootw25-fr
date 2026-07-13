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
    # A page can repeat a heading (contact-us has two "Email"/"Phone Number"
    # pairs): recurring section slugs get a deterministic -2/-3... suffix so
    # ids never collide across the repeats.
    section_uses = {}
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
            base = slugify(en)
            section_uses[base] = section_uses.get(base, 0) + 1
            section = (base if section_uses[base] == 1
                       else f"{base}-{section_uses[base]}")
            counters = {}
        counters[tag] = counters.get(tag, 0) + 1
        # headings restart the section, so their own id uses the new section
        entries.append(_entry(f"{slug} § {section} § {tag}{counters[tag]}",
                              section, tag, en))

    ids = [e["id"] for e in entries]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate ids in page '{slug}': {sorted(dupes)}")
    return entries, new_global


def merge_catalog(fresh_entries, old_entries):
    """fresh_entries: freshly extracted entries (fr="", status="pending").
    old_entries: entries loaded from the existing catalog file on disk (or
    [] if there isn't one yet). Returns fresh_entries, mutated in place, so
    that re-running extract never silently discards translators' work: for
    any entry whose id AND normalized en both still match an old entry, its
    fr/status are carried over. An entry whose en text changed (even under
    the same id) is left as fr=""/status="pending" -- the old translation
    no longer applies and must be redone.
    """
    old_by_id = {e["id"]: e for e in old_entries}
    for e in fresh_entries:
        old = old_by_id.get(e["id"])
        if old is not None and norm(old["en"]) == norm(e["en"]):
            e["fr"] = old["fr"]
            e["status"] = old["status"]
    return fresh_entries


def main():
    Path("catalog").mkdir(exist_ok=True)
    global_entries, global_index = [], {}
    for slug in PAGES:
        html = Path(f"en/{slug}.html").read_text(encoding="utf-8")
        entries, new_global = extract_page(slug, html, global_index)
        for g in new_global:
            global_entries.append(g)
            global_index[norm(g["en"])] = g
        cat_path = Path(f"catalog/{slug}.json")
        if cat_path.exists():
            old_entries = json.loads(cat_path.read_text(encoding="utf-8"))
            entries = merge_catalog(entries, old_entries)
        cat_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"{slug}: {len(entries)} strings")
    gids = [g["id"] for g in global_entries]
    gdupes = {i for i in gids if gids.count(i) > 1}
    if gdupes:
        raise ValueError(f"duplicate ids in _global: {sorted(gdupes)}")
    global_path = Path("catalog/_global.json")
    if global_path.exists():
        old_global = json.loads(global_path.read_text(encoding="utf-8"))
        global_entries = merge_catalog(global_entries, old_global)
    global_path.write_text(
        json.dumps(global_entries, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"_global: {len(global_entries)} strings")


if __name__ == "__main__":
    sys.exit(main())
