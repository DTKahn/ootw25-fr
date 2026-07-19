from bs4 import BeautifulSoup

from scripts.common import walk
from scripts.extract_live_fr import align_nodes

IDENTICAL_A = "<html><body><h2>Title</h2><p>One</p><p>Two</p></body></html>"
IDENTICAL_B = "<html><body><h2>Titre</h2><p>Un</p><p>Deux</p></body></html>"


def test_align_nodes_identical_structure_full_mapping():
    """Same DOM shape on both sides: every en position maps 1:1 to the
    corresponding live position."""
    a = walk(BeautifulSoup(IDENTICAL_A, "lxml"))
    b = walk(BeautifulSoup(IDENTICAL_B, "lxml"))
    assert len(a) == len(b) == 3
    assert align_nodes(a, b) == {0: 0, 1: 1, 2: 2}


EXTRA_B = ("<html><body><h2>Titre</h2><blockquote>Extra info</blockquote>"
           "<p>Un</p><p>Deux</p></body></html>")


def test_align_nodes_extra_node_in_live_uses_sequencematcher():
    """The live fixture has an extra <blockquote> node with no en
    counterpart, so lengths differ and the SequenceMatcher path kicks in.
    The h2 and both <p>s still line up correctly across the gap; there's
    simply no mapping produced for the extra node (it has no en index to
    receive it)."""
    a = walk(BeautifulSoup(IDENTICAL_A, "lxml"))
    b = walk(BeautifulSoup(EXTRA_B, "lxml"))
    assert len(a) == 3
    assert len(b) == 4
    mapping = align_nodes(a, b)
    assert mapping[0] == 0  # h2 <-> h2
    assert mapping[1] == 2  # first <p> <-> first <p> (after the blockquote)
    assert mapping[2] == 3  # second <p> <-> second <p>
    assert 1 not in mapping.values()  # the blockquote is never targeted
