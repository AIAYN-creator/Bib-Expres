import json

import pytest

from bib_expres.export import infer_format, to_bibtex, to_csljson, to_ris, write
from bib_expres.models import DiscoveryMode, Paper


def _paper(**overrides):
    defaults = dict(
        openalex_id="W1",
        doi="10.1/abc",
        title="A Great Paper",
        authors=["Jane Smith", "John Doe"],
        year=2021,
        venue="Journal of Things",
        concepts=[],
        citation_count=5,
        generation=0,
        discovered_via=DiscoveryMode.ROOT,
    )
    defaults.update(overrides)
    return Paper(**defaults)


def test_to_bibtex_includes_core_fields():
    bib = to_bibtex([_paper()])
    assert "@article{smith2021," in bib
    assert "title = {A Great Paper}" in bib
    assert "author = {Jane Smith and John Doe}" in bib
    assert "doi = {10.1/abc}" in bib
    assert "url = {https://doi.org/10.1/abc}" in bib


def test_to_bibtex_disambiguates_duplicate_keys():
    a = _paper(doi="10.1/a")
    b = _paper(doi="10.1/b")
    bib = to_bibtex([a, b])
    assert "@article{smith2021," in bib
    assert "@article{smith2021a," in bib


def test_to_bibtex_empty_list():
    assert to_bibtex([]) == ""


def test_to_bibtex_escapes_braces_and_backslashes():
    paper = _paper(title=r"A {weird} \title")
    bib = to_bibtex([paper])
    assert r"title = {A \{weird\} \textbackslash{}title}" in bib


def test_to_ris_includes_core_fields():
    ris = to_ris([_paper()])
    assert "TY  - JOUR" in ris
    assert "TI  - A Great Paper" in ris
    assert "AU  - Jane Smith" in ris
    assert "AU  - John Doe" in ris
    assert "PY  - 2021" in ris
    assert "T2  - Journal of Things" in ris
    assert "DO  - 10.1/abc" in ris
    assert "UR  - https://doi.org/10.1/abc" in ris
    assert "ER  -" in ris


def test_to_ris_empty_list():
    assert to_ris([]) == ""


def test_to_ris_omits_missing_fields():
    paper = _paper(doi=None, venue=None)
    ris = to_ris([paper])
    assert "DO  -" not in ris
    assert "UR  -" not in ris
    assert "T2  -" not in ris


def test_to_csljson_includes_core_fields():
    entries = json.loads(to_csljson([_paper()]))
    assert len(entries) == 1
    entry = entries[0]
    assert entry["type"] == "article-journal"
    assert entry["title"] == "A Great Paper"
    assert entry["author"] == [
        {"family": "Smith", "given": "Jane"},
        {"family": "Doe", "given": "John"},
    ]
    assert entry["issued"] == {"date-parts": [[2021]]}
    assert entry["container-title"] == "Journal of Things"
    assert entry["DOI"] == "10.1/abc"
    assert entry["URL"] == "https://doi.org/10.1/abc"


def test_to_csljson_empty_list():
    assert to_csljson([]) == "[]"


def test_write_dispatches_by_format(tmp_path):
    path = tmp_path / "out.ris"
    write([_paper()], str(path), format="ris")
    assert "TY  - JOUR" in path.read_text(encoding="utf-8")


def test_write_rejects_unknown_format(tmp_path):
    with pytest.raises(ValueError, match="formato desconocido"):
        write([_paper()], str(tmp_path / "out.xyz"), format="nope")


def test_infer_format_by_extension():
    assert infer_format("out.bib") == "bibtex"
    assert infer_format("out.ris") == "ris"
    assert infer_format("out.json") == "csljson"
    assert infer_format("out.unknown") == "bibtex"
