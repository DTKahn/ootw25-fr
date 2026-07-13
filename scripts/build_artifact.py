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
        entries = json.loads(p.read_text(encoding="utf-8"))
        rows = []
        for e in entries:
            rows.append(
                "<tr><td class='id' title='{i}'>{i}</td><td>{en}</td>"
                "<td class='fr' contenteditable='plaintext-only' data-id='{i}'>{fr}</td>"
                "<td class='status'>{st}</td></tr>".format(
                    i=html.escape(e["id"]), en=html.escape(e["en"]),
                    fr=html.escape(e["fr"]), st=html.escape(e["status"])))
        blocks.append(
            f"<details{' open' if slug == '_global' else ''}>"
            f"<summary>{html.escape(slug)} ({len(entries)})</summary>"
            f"<table><tr><th>ID</th><th>English</th><th>Français (modifiable)</th>"
            f"<th></th></tr>{''.join(rows)}</table></details>")
    Path(out_path).write_text(TEMPLATE.format(tables="".join(blocks)),
                              encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    build()
