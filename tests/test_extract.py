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


FORM_FIXTURE = """
<html><head><title>Contact</title></head>
<body>
<h2>Get in Touch</h2>
<form class="srfm-form">
<input name="form-id" type="hidden" value="2395">
<input type="text" placeholder="First Name *">
<div class="srfm-error-wrap">
  <div class="srfm-error-message" data-error-msg="This field is required.">This field is required.</div>
</div>
<textarea placeholder="Message"></textarea>
<label class="srfm-cbx" for="x"><span class="srfm-block-label">Consent: I agree to the <a href="/privacy-policy">Privacy Policy</a></span></label>
<div class="srfm-validation-error" style="display: none;">Please verify that you are not a robot.</div>
<button class="srfm-submit-button"><div class="srfm-submit-wrap">SEND NOW<div class="srfm-loader"></div></div></button>
<input type="submit" value="Send">
</form>
</body></html>
"""


def test_walk_captures_form_ui_text():
    """SureForms contact-form pattern: placeholders and submit-input values
    are attribute-based strings (kind "attr" with the attribute recorded so
    apply.py can write them back); labels, error/validation message divs and
    the submit <button> text are block nodes. Hidden-input values (form-id
    plumbing) must never be captured.
    """
    soup = BeautifulSoup(FORM_FIXTURE, "lxml")
    nodes = walk(soup)
    texts = [norm(node_en(n)) for n in nodes]
    assert texts == [
        "Get in Touch",
        "First Name *",                              # input placeholder
        "This field is required.",                   # data-error-msg attr
        "This field is required.",                   # error div text
        "Message",                                   # textarea placeholder
        '<span class="srfm-block-label">Consent: I agree to the'
        ' <a href="/privacy-policy">Privacy Policy</a></span>',  # label
        "Please verify that you are not a robot.",   # validation div text
        "SEND NOW",                                  # <button> text
        "Send",                                      # input[type=submit] value
    ]
    kinds = [n.kind for n in nodes]
    assert kinds == ["block", "attr", "attr", "block", "attr",
                     "block", "block", "block", "attr"]
    attrs = [n.attr for n in nodes]
    assert attrs == [None, "placeholder", "data-error-msg", None,
                     "placeholder", None, None, None, "value"]
    assert "2395" not in " ".join(texts)


def test_extract_page_form_tags_and_ids():
    entries, _ = extract_page("contact", FORM_FIXTURE, global_index={})
    ids = [e["id"] for e in entries]
    assert "contact § get-in-touch § placeholder1" in ids
    assert "contact § get-in-touch § placeholder2" in ids
    assert "contact § get-in-touch § label1" in ids
    assert "contact § get-in-touch § button1" in ids   # <button> text
    assert "contact § get-in-touch § button2" in ids   # input[type=submit]
    assert "contact § get-in-touch § error-msg1" in ids
    by_id = {e["id"]: e for e in entries}
    assert by_id["contact § get-in-touch § placeholder1"]["en"] == "First Name *"
    assert by_id["contact § get-in-touch § button1"]["en"] == "SEND NOW"
    assert by_id["contact § get-in-touch § button2"]["en"] == "Send"


REPEATED_HEADING_FIXTURE = """
<html><head><title>Contact</title></head>
<body>
<h3>Email</h3>
<p>info@canhist.ca</p>
<h3>Phone Number</h3>
<p>555-0001</p>
<h3>Email</h3>
<p>mcyu@mcmaster.ca</p>
<h3>Phone Number</h3>
<p>555-0002</p>
</body></html>
"""


def test_repeated_headings_get_distinct_sections_and_unique_ids():
    """contact-us has two Email/Phone Number heading pairs; both used to
    slugify to the same section, silently assigning the same id (e.g.
    "contact-us § email § p1") to two different strings. Recurring section
    slugs must be disambiguated deterministically and all ids unique.
    """
    entries, _ = extract_page("contact", REPEATED_HEADING_FIXTURE,
                              global_index={})
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids)), f"duplicate ids: {ids}"
    by_id = {e["id"]: e for e in entries}
    assert by_id["contact § email § p1"]["en"] == "info@canhist.ca"
    assert by_id["contact § phone-number § p1"]["en"] == "555-0001"
    assert by_id["contact § email-2 § p1"]["en"] == "mcyu@mcmaster.ca"
    assert by_id["contact § phone-number-2 § p1"]["en"] == "555-0002"
