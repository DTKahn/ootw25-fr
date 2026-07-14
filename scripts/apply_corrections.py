import json
import sys
from pathlib import Path


def apply_corrections(catalogs: dict, corrections: dict) -> tuple[int, list[str]]:
    """catalogs: {slug: entries}. Mutates in place.

    Corrections are plain text (see build_artifact.py). An entry whose
    English source carries markup (`<` in en) has a tagged `fr` that the
    review page shows as stripped plain text; writing the plain-text
    correction straight over it would destroy the formatting. Those
    corrections are skipped here and returned for the caller to report —
    they need to be re-fit with markup before they can be applied.

    Returns (count applied, list of skipped ids needing markup re-fit).
    """
    index = {e["id"]: e for entries in catalogs.values() for e in entries}
    applied = 0
    needs_markup_refit = []
    for cid, fr in corrections.items():
        e = index.get(cid)
        if e is None:
            sys.exit(f"unknown string id: {cid!r}")
        if not isinstance(fr, str):
            sys.exit(f"correction for {cid!r} is not a string: {fr!r}")
        if not fr.strip():
            sys.exit(f"empty correction for {cid!r} — refusing")
        if "<" in e["en"]:
            needs_markup_refit.append(cid)
            continue
        if e["fr"] != fr:
            e["fr"] = fr
            e["status"] = "corrected"
            applied += 1
    return applied, needs_markup_refit


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python -m scripts.apply_corrections corrections.json")
    corrections = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    catalogs = {}
    for f in sorted(Path("catalog").glob("*.json")):
        catalogs[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    n, needs_markup_refit = apply_corrections(catalogs, corrections)
    for slug, entries in catalogs.items():
        Path(f"catalog/{slug}.json").write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8")
    print(f"applied {n} corrections across {len(corrections)} submitted")
    if needs_markup_refit:
        ids = "\n".join(f"  - {cid}" for cid in needs_markup_refit)
        sys.exit(
            "NEEDS MARKUP RE-FIT: the following corrections were NOT "
            "applied because their entries carry HTML formatting that the "
            "plain-text correction cannot simply overwrite:\n"
            f"{ids}\n"
            "Re-fit these with markup preserved and resubmit.")


if __name__ == "__main__":
    main()
