"""Snapshot the CURRENT live French pages from https://ootw25.ca/fr/ into
fr-live/<slug>.html, for display-only reference in the review artifact.

This is NOT a translation source: catalog/*.json are never touched by this
script or by anything downstream of fr-live/. See scripts/extract_live_fr.py
and scripts/build_artifact.py.
"""
import subprocess
import sys
from pathlib import Path

from scripts.pages import PAGES


def live_fr_url(slug: str) -> str:
    if slug == "index":
        return "https://ootw25.ca/fr/"
    return f"https://ootw25.ca/fr/{slug}/"


def main():
    Path("fr-live").mkdir(exist_ok=True)
    ok, failed = [], []
    for slug in PAGES:
        url = live_fr_url(slug)
        out_path = Path(f"fr-live/{slug}.html")
        result = subprocess.run(
            ["curl", "-sSfL", "-o", str(out_path), url],
            capture_output=True, text=True)
        if result.returncode != 0:
            print(f"WARNING: failed to fetch {url}: {result.stderr.strip()}",
                  file=sys.stderr)
            if out_path.exists():
                out_path.unlink()
            failed.append(slug)
            continue
        ok.append(slug)
        print(f"{slug}: fetched {url}")
    print(f"\n{len(ok)}/{len(PAGES)} live French pages downloaded"
          f"{'; missing: ' + ', '.join(failed) if failed else ''}")


if __name__ == "__main__":
    sys.exit(main())
