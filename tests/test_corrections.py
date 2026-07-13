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
    n = apply_corrections(cats, {"my-page § s § p1": "Bonjour à tous"})
    assert n == 1
    assert cats["my-page"][0]["fr"] == "Bonjour à tous"
    assert cats["my-page"][0]["status"] == "corrected"
    assert cats["my-page"][1]["status"] == "translated"


def test_unknown_id_fails_loudly():
    with pytest.raises(SystemExit):
        apply_corrections(_cats(), {"nope § x § p9": "..."})


def test_empty_correction_rejected():
    with pytest.raises(SystemExit):
        apply_corrections(_cats(), {"my-page § s § p1": "  "})
