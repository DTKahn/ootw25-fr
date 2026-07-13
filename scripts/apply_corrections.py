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
        if not isinstance(fr, str):
            sys.exit(f"correction for {cid!r} is not a string: {fr!r}")
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
    corrections = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    catalogs = {}
    for f in sorted(Path("catalog").glob("*.json")):
        catalogs[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    n = apply_corrections(catalogs, corrections)
    for slug, entries in catalogs.items():
        Path(f"catalog/{slug}.json").write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8")
    print(f"applied {n} corrections across {len(corrections)} submitted")


if __name__ == "__main__":
    main()
