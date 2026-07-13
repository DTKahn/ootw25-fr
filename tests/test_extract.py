from bs4 import BeautifulSoup
from scripts.common import walk, node_en, norm
from scripts.extract import extract_page

FIXTURE = """
<html><head><title>My Page - OOTW25</title>
<meta name="description" content="A test page."></head>
<body>
<header data-elementor-type="header"><nav><ul>
  <li><a href="https://ootw25.ca/educators/">Educators</a></li>
</ul></nav></header>
<h2>The Mission</h2>
<p>First paragraph with <strong>bold</strong> text.</p>
<p>Second paragraph.</p>
<ul><li>A list item.</li></ul>
<a class="elementor-button" href="#"><span class="elementor-button-text">Learn More</span></a>
<img src="x.jpg" alt="An astronaut in space.">
<h2>Partners</h2>
<p>Learn More</p>
<script>var ignored = "yes";</script>
<footer><p>© 2026 OOTW25</p></footer>
</body></html>
"""

def test_walk_finds_translatable_nodes_in_order():
    soup = BeautifulSoup(FIXTURE, "lxml")
    nodes = walk(soup)
    texts = [norm(node_en(n)) for n in nodes]
    assert texts == [
        "Educators",
        "The Mission",
        "First paragraph with <strong>bold</strong> text.",
        "Second paragraph.",
        "A list item.",
        "Learn More",
        "An astronaut in space.",
        "Partners",
        "Learn More",
        "© 2026 OOTW25",
    ]
    assert [n.is_global for n in nodes] == [
        True, False, False, False, False, False, False, False, False, True]

def test_extract_page_ids_sections_and_global_dedup():
    entries, glob = extract_page("my-page", FIXTURE, global_index={})
    ids = [e["id"] for e in entries]
    assert "my-page § meta § title" in ids
    assert "my-page § meta § description" in ids
    assert "my-page § the-mission § p1" in ids
    assert "my-page § the-mission § p2" in ids
    assert "my-page § the-mission § li1" in ids
    assert "my-page § the-mission § button1" in ids
    assert "my-page § the-mission § img1" in ids
    assert "my-page § partners § p1" in ids
    assert [g["id"] for g in glob] == ["global § chrome § a1", "global § chrome § p1"]
    by_id = {e["id"]: e for e in entries}
    assert by_id["my-page § the-mission § p1"]["en"] == \
        "First paragraph with <strong>bold</strong> text."
    assert all(e["fr"] == "" and e["status"] == "pending" for e in entries)
    # second call with populated global_index yields no new global entries
    gi = {norm(g["en"]): g for g in glob}
    _, glob2 = extract_page("my-page", FIXTURE, global_index=gi)
    assert glob2 == []


DROPDOWN_FIXTURE = """
<html><head><title>Dropdown Page</title></head>
<body>
<header data-elementor-type="header"><nav><ul>
  <li id="menu-item-3188" class="menu-item-has-children">
    <a aria-expanded="false" class="menu-link">ABOUT<span class="dropdown-menu-toggle">
      <span class="ast-icon icon-arrow"><svg></svg></span>
    </span></a>
    <button class="ast-menu-toggle" aria-label="Toggle Menu"><span class="ast-icon icon-arrow"><svg></svg></span></button>
    <ul class="sub-menu">
      <li><a href="https://ootw25.ca/who-are-we/">Who Are We</a></li>
      <li><a href="https://ootw25.ca/partners/">Partners</a></li>
    </ul>
  </li>
</ul></nav></header>
<h2>Body</h2>
<p>Some text.</p>
</body></html>
"""


def test_walk_captures_dropdown_menu_label_and_submenu_items():
    """Astra/Elementor mega-menu pattern: an <li> has a direct <a> label
    ("ABOUT") plus a sibling <ul class="sub-menu"> of its own <li><a>
    items. The old code skipped the whole outer <li> because it contains
    a nested block-tag (li) descendant, silently dropping the "ABOUT"
    label. The label and every submenu item text must all be captured.
    """
    soup = BeautifulSoup(DROPDOWN_FIXTURE, "lxml")
    nodes = walk(soup)
    texts = [norm(node_en(n)) for n in nodes]
    assert texts[:3] == ["ABOUT", "Who Are We", "Partners"]
    assert all(n.is_global for n in nodes[:3])
