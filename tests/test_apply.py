import pytest
from scripts.apply import apply_page, build_url_map, check_complete
from scripts.extract import extract_page
from tests.test_extract import FIXTURE, FORM_FIXTURE


def _translated():
    entries, glob = extract_page("my-page", FIXTURE, global_index={})
    fr = {
        "my-page § meta § title": "Ma page - OOTW25",
        "my-page § meta § description": "Une page de test.",
        "my-page § the-mission § p1":
            "Premier paragraphe avec du texte en <strong>gras</strong>.",
        "my-page § the-mission § p2": "Deuxième paragraphe.",
        "my-page § the-mission § li1": "Un élément de liste.",
        "my-page § the-mission § button1": "En savoir plus",
        "my-page § the-mission § img1": "Un astronaute dans l'espace.",
        "my-page § the-mission § h21": "La mission",
        "my-page § partners § h21": "Partenaires",
        "my-page § partners § p1": "En savoir plus",
        "global § chrome § a1": "Éducateurs",
        "global § chrome § p1": "© 2026 OOTW25",
    }
    for e in entries + glob:
        e["fr"] = fr[e["id"]]
        e["status"] = "translated"
    return entries, glob


def test_apply_replaces_text_sets_lang_rewrites_links():
    entries, glob = _translated()
    url_map = build_url_map({"educators": "https://ootw25.ca/educators/"})
    out = apply_page("my-page", FIXTURE, entries,
                     {e["en"]: e for e in glob}, url_map)
    assert 'lang="fr-CA"' in out
    assert "<title>Ma page - OOTW25</title>" in out
    assert "Deuxième paragraphe." in out
    assert "du texte en <strong>gras</strong>" in out
    assert 'alt="Un astronaute dans l\'espace."' in out
    assert 'href="educators.html"' in out
    assert "First paragraph" not in out and "Second paragraph" not in out
    assert 'var ignored = "yes";' in out  # scripts untouched


def test_apply_writes_translated_attr_back_to_element():
    """Placeholder/value/data-*-msg strings are kind "attr" nodes; apply
    must write the French translation back to the element's own attribute
    (node.attr), not into its inner HTML."""
    entries, glob = extract_page("contact", FORM_FIXTURE, global_index={})
    fr = {
        "contact § meta § title": "Contact",
        "contact § get-in-touch § h21": "Contactez-nous",
        "contact § get-in-touch § placeholder1": "Prénom *",
        "contact § get-in-touch § error-msg1": "Ce champ est obligatoire.",
        "contact § get-in-touch § div1": "Ce champ est obligatoire.",
        "contact § get-in-touch § placeholder2": "Message",
        "contact § get-in-touch § label1":
            '<span class="srfm-block-label">Consentement : j\'accepte la'
            ' <a href="/privacy-policy">politique de confidentialité</a></span>',
        "contact § get-in-touch § div2":
            "Veuillez vérifier que vous n'êtes pas un robot.",
        "contact § get-in-touch § button1": "ENVOYER",
        "contact § get-in-touch § button2": "Envoyer",
    }
    by_id = {e["id"]: e for e in entries}
    for id_, fr_text in fr.items():
        by_id[id_]["fr"] = fr_text
        by_id[id_]["status"] = "translated"
    for e in entries:
        assert e["fr"], f"missing fr fixture for {e['id']}"
    out = apply_page("contact", FORM_FIXTURE, entries, {}, {})
    assert 'placeholder="Prénom *"' in out
    assert 'placeholder="Message"' in out
    assert 'value="Envoyer"' in out
    assert 'data-error-msg="Ce champ est obligatoire."' in out
    assert "First Name" not in out


def test_refuses_untranslated():
    entries, glob = _translated()
    entries[3]["fr"] = ""
    entries[3]["status"] = "pending"
    with pytest.raises(SystemExit):
        check_complete([("my-page", entries), ("_global", glob)])


def test_identical_whitelisted_string_passes():
    entries, glob = _translated()
    e = next(x for x in entries if x["en"] == "Learn More" and "partners" in x["id"])
    e["fr"] = ""  # not translated, but en text is whitelisted below
    check_complete([("my-page", entries), ("_global", glob)],
                   identical_ok={"Learn More"})
    assert e["fr"] == "Learn More"
