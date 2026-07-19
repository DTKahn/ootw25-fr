import html
import json
import re
from pathlib import Path

from scripts.pages import PAGES

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def plain(s: str) -> str:
    """Plain-text form of a (possibly markup-bearing) string: tags stripped,
    whitespace runs collapsed. Used both for display and for comparing the
    proposed translation against the live-site one."""
    no_tags = _TAG_RE.sub("", s)
    # Catalog strings carry source-HTML entities (&amp;, &#8217;…): decode
    # them so cells show real characters; strip_tags() re-escapes exactly
    # once for safe insertion.
    return _WS_RE.sub(" ", html.unescape(no_tags)).strip()


def strip_tags(s: str) -> str:
    """HTML-escaped plain(), safe to insert into a table cell as text.
    Guillemets and accented characters pass through untouched."""
    return html.escape(plain(s))

TEMPLATE = """<title>OOTW25 — Révision de la traduction française</title>
<style>
  body {{ font: 15px/1.5 system-ui, sans-serif; margin: 0 auto; max-width: 1500px;
         padding: 1rem; }}
  h1 {{ font-size: 1.3rem; }}
  details {{ margin: .6rem 0; border: 1px solid #8884; border-radius: 8px;
             overflow-x: auto; }}
  summary {{ padding: .5rem .8rem; cursor: pointer; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .92em;
           table-layout: fixed; min-width: 760px; }}
  col.c-id {{ width: 14%; }}  col.c-en {{ width: 26%; }}
  col.c-live {{ width: 26%; }} col.c-fr {{ width: 26%; }}
  col.c-st {{ width: 8%; }}
  th, td {{ border-top: 1px solid #8883; padding: .45rem .6rem;
            vertical-align: top; text-align: left;
            overflow-wrap: break-word; }}
  td.id {{ font-family: ui-monospace, monospace; font-size: .78em; opacity: .7;
           overflow: hidden; word-break: break-all; }}
  td.fr {{ white-space: pre-wrap; }}
  td.fr[contenteditable]:focus {{ outline: 2px solid #4a90d9; }}
  td.fr.dirty {{ background: #fde68a55; }}
  td.live-fr {{ white-space: pre-wrap; opacity: .7; }}
  tr.differs {{ background: #dbeafe66; }}
  tr.differs td.id {{ border-left: 4px double #8886; }}
  .diff-mark {{ display: inline-block; font-size: .85em; padding: .1rem .4rem;
                border-radius: 4px; background: #bfdbfe88; cursor: help;
                font-weight: 600; }}
  @media (prefers-color-scheme: dark) {{ tr.differs {{ background: #1e3a5f55; }}
    .diff-mark {{ background: #1d4ed855; }} }}
  .badge {{ display: inline-block; font-size: .85em; padding: .1rem .4rem;
            border-radius: 4px; background: #4a90d922; cursor: help; }}
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
<p>Les cellules affichent le texte seul, sans balises. Les chaînes qui
comportent une mise en forme (gras, liens, etc.) sont marquées d'un badge
« ⚑ mise en forme » : la mise en forme d'origine est automatiquement
réappliquée après l'application des corrections, vous n'avez donc pas à vous
en préoccuper — modifiez simplement le texte. La colonne « Français actuel
(site) », lorsqu'elle est présente, affiche à titre de référence uniquement
la traduction française actuellement en ligne sur le site; elle n'est pas
modifiable et n'a aucune influence sur la traduction proposée. Les lignes où
la traduction proposée diffère de la traduction actuelle du site sont
surlignées en bleu et marquées « ≠ à revoir » (avec une double bordure à
gauche de la ligne). Modifiez le
texte français directement dans les cellules de la colonne « Français
(modifiable) »; les cellules modifiées sont surlignées. Cliquez « Exporter
les corrections », puis collez le résultat dans la conversation Claude
Code.</p>
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


def build(catalog_dir="catalog", out_path="review.html", live_fr_path="live-fr.json"):
    order = ["_global"] + list(PAGES)
    live_fr_file = Path(live_fr_path)
    live_fr = (json.loads(live_fr_file.read_text(encoding="utf-8"))
               if live_fr_file.exists() else None)
    live_fr_th = ("<th>Français actuel (site)</th>" if live_fr is not None else "")
    # Fixed-layout column widths (colgroup) so long strings wrap inside
    # their cells instead of blowing the table out of its card.
    if live_fr is not None:
        colgroup = ("<colgroup><col class='c-id'><col class='c-en'>"
                    "<col class='c-live'><col class='c-fr'>"
                    "<col class='c-st'></colgroup>")
    else:
        colgroup = ("<colgroup><col class='c-id'><col class='c-en'>"
                    "<col class='c-fr' style='width:40%'>"
                    "<col class='c-st'></colgroup>")
    blocks = []
    for slug in order:
        p = Path(catalog_dir) / f"{slug}.json"
        if not p.exists():
            continue
        entries = json.loads(p.read_text(encoding="utf-8"))
        rows = []
        for e in entries:
            # en/fr are rendered as plain text: tags are stripped and the
            # result is html-escaped, so site markup (including inline
            # style="color:..." spans) never leaks into the review table.
            # Entries whose English source carries markup get a badge
            # instead, since their formatting is reapplied automatically
            # after corrections are applied (see apply_corrections.py).
            has_markup = "<" in e["en"]
            badge = (
                " <span class='badge' title=\"Cette chaîne comporte une mise "
                "en forme (gras, lien, etc.) qui sera automatiquement "
                "réappliquée après l'application de la correction.\">"
                "⚑ mise en forme</span>" if has_markup else "")
            # Read-only reference column: the CURRENT live-site French
            # string for this id, if we have one (live-fr.json is generated
            # by scripts/extract_live_fr.py from a snapshot of
            # https://ootw25.ca/fr/ -- it never feeds back into the
            # catalog, it's display-only). Empty cell when there's no key.
            live_fr_td = ""
            differs = False
            if live_fr is not None:
                live_val = live_fr.get(e["id"], "")
                # Row-level review flag: the proposed translation differs
                # from the live site's current French (plain-text compare;
                # no flag when the live string is simply missing).
                differs = bool(live_val) and plain(live_val) != plain(e["fr"])
                live_fr_td = ("<td class='live-fr'>{v}</td>"
                               .format(v=strip_tags(live_val)))
            diff_mark = (
                " <span class='diff-mark' title=\"La traduction proposée "
                "diffère de la traduction actuellement en ligne — à "
                "comparer.\">≠ à revoir</span>" if differs else "")
            rows.append(
                "<tr{cls}><td class='id' title='{i}'>{i}</td><td>{en}</td>{live}"
                "<td class='fr' contenteditable='plaintext-only' data-id='{i}'>{fr}</td>"
                "<td class='status'>{st}{badge}{diff}</td></tr>".format(
                    cls=" class='differs'" if differs else "",
                    i=html.escape(e["id"]), en=strip_tags(e["en"]),
                    live=live_fr_td,
                    fr=strip_tags(e["fr"]), st=html.escape(e["status"]),
                    badge=badge, diff=diff_mark))
        blocks.append(
            f"<details{' open' if slug == '_global' else ''}>"
            f"<summary>{html.escape(slug)} ({len(entries)})</summary>"
            f"<table>{colgroup}<tr><th>ID</th><th>English</th>{live_fr_th}"
            f"<th>Français (modifiable)</th>"
            f"<th></th></tr>{''.join(rows)}</table></details>")
    Path(out_path).write_text(TEMPLATE.format(tables="".join(blocks)),
                              encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    build()
