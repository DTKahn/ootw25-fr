import json
import pytest
from scripts.apply_corrections import apply_corrections


def _cats():
    return {"my-page": [
        {"id": "my-page § s § p1", "section": "s", "tag": "p",
         "en": "Hello", "fr": "Bonjour", "status": "translated"},
        {"id": "my-page § s § p2", "section": "s", "tag": "p",
         "en": "World", "fr": "Monde", "status": "translated"},
    ]}


def test_applies_and_marks_corrected():
    cats = _cats()
    n, needs_refit = apply_corrections(cats, {"my-page § s § p1": "Bonjour à tous"})
    assert n == 1
    assert needs_refit == []
    assert cats["my-page"][0]["fr"] == "Bonjour à tous"
    assert cats["my-page"][0]["status"] == "corrected"
    assert cats["my-page"][1]["status"] == "translated"


def test_tagged_entry_correction_skipped_and_reported():
    """A correction targeting an entry whose `en` carries markup must not
    overwrite the tagged `fr` with plain text; it should be reported back
    to the caller instead of applied, while a plain-text sibling correction
    in the same batch still goes through."""
    cats = {"my-page": [
        {"id": "my-page § s § plain", "section": "s", "tag": "p",
         "en": "Hello", "fr": "Bonjour", "status": "translated"},
        {"id": "my-page § s § tagged", "section": "s", "tag": "p",
         "en": "Hello <strong>world</strong>",
         "fr": "Bonjour <strong>monde</strong>", "status": "translated"},
    ]}
    n, needs_refit = apply_corrections(cats, {
        "my-page § s § plain": "Bonjour à tous",
        "my-page § s § tagged": "Bonjour tout le monde",
    })
    assert n == 1
    assert needs_refit == ["my-page § s § tagged"]
    assert cats["my-page"][0]["fr"] == "Bonjour à tous"
    assert cats["my-page"][0]["status"] == "corrected"
    assert cats["my-page"][1]["fr"] == "Bonjour <strong>monde</strong>"
    assert cats["my-page"][1]["status"] == "translated"


def test_unknown_id_fails_loudly():
    with pytest.raises(SystemExit):
        apply_corrections(_cats(), {"nope § x § p9": "..."})


def test_empty_correction_rejected():
    with pytest.raises(SystemExit):
        apply_corrections(_cats(), {"my-page § s § p1": "  "})


def test_non_string_correction_rejected():
    """A corrections.json with a non-string value (e.g. a number, list, or
    null from a malformed export) must be rejected with a clean error
    instead of crashing on fr.strip()."""
    with pytest.raises(SystemExit):
        apply_corrections(_cats(), {"my-page § s § p1": 123})
    with pytest.raises(SystemExit):
        apply_corrections(_cats(), {"my-page § s § p1": None})
    with pytest.raises(SystemExit):
        apply_corrections(_cats(), {"my-page § s § p1": ["Bonjour"]})
