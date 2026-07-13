import copy
import re
from collections import namedtuple

Node = namedtuple("Node", "el kind is_global")

BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "figcaption"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
SKIP_ANCESTORS = {"script", "style", "noscript", "template"}
GLOBAL_TAGS = {"header", "footer", "nav"}
# Purely decorative markup (submenu-toggle carets, icon svgs) that carries no
# translatable text. Stripped from extracted "en" HTML so translators never
# have to reproduce icon markup verbatim, e.g. Astra's mega-menu dropdown
# toggles: <a>Label<span class="dropdown-menu-toggle"><svg>...</svg></span></a>
DECORATIVE_CLASSES = {"dropdown-menu-toggle", "ast-icon"}


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


def _strip_decorative(el):
    """Return a detached copy of el with decorative icon/toggle descendants
    (svg icons, dropdown-toggle wrappers) removed, so their markup never
    leaks into extracted "en" text."""
    clone = copy.copy(el)
    targets = [d for d in clone.find_all(True)
               if d.name == "svg" or (set(d.get("class") or []) & DECORATIVE_CLASSES)]
    for t in targets:
        if t.parent is not None:
            t.decompose()
    return clone


def node_en(node: Node) -> str:
    if node.kind == "img":
        return node.el.get("alt", "").strip()
    return _strip_decorative(node.el).decode_contents().strip()


def walk(soup) -> list:
    """All translatable nodes in document order. Shared by extract and apply."""
    out = []
    body = soup.body or soup
    for el in body.find_all(True):
        if any(a.name in SKIP_ANCESTORS for a in el.parents):
            continue
        is_block = el.name in BLOCK_TAGS or _is_button_text(el)
        if is_block:
            # Astra/Elementor dropdown-menu pattern: <li><a>Label</a>
            # <button>toggle</button><ul class="sub-menu">...</ul></li>.
            # The outer <li> has a nested block-tag (its submenu <li>s), so
            # the generic "innermost blocks only" rule below would skip it
            # entirely -- but its direct <a> label sits *outside* that
            # nested block content and must still be captured. The nested
            # submenu <li>s are picked up on their own iterations of this
            # loop, unaffected by this branch.
            if el.name == "li":
                direct_a = next(
                    (c for c in el.children if getattr(c, "name", None) == "a"),
                    None)
                nested_block = el.find(list(BLOCK_TAGS))
                if (direct_a is not None and nested_block is not None
                        and nested_block not in direct_a.find_all(True)):
                    if (norm(direct_a.get_text())
                            and not any(_is_button_text(a) for a in direct_a.parents)):
                        out.append(Node(direct_a, "block", _is_global(el)))
                    continue
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
