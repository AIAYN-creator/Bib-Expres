from bib_expres.export import to_bibtex
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
