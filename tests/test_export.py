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


# -- xlsx -----------------------------------------------------------------------


def _read_xlsx(path):
    from openpyxl import load_workbook

    return load_workbook(path).active


def test_write_xlsx_columns_and_values(tmp_path):
    out = tmp_path / "rev.xlsx"
    paper = _paper(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani", "Noam Shazeer"],
        doi="10.48550/arxiv.1706.03762",
        relevance_score=0.8234,
        topic="Natural Language Processing Techniques",
        keywords=["transformer", "self-attention"],
    )
    write([paper], str(out), format="xlsx")

    ws = _read_xlsx(out)
    headers = [c.value for c in ws[1]]
    assert headers == [
        "Título", "Autores", "DOI", "Tema", "Palabras clave", "Relevancia",
        "Acceso", "Enlace de acceso", "Otras notas",
    ]
    row = [c.value for c in ws[2]]
    assert row[0] == "Attention Is All You Need"
    assert row[1] == "Ashish Vaswani; Noam Shazeer"
    assert row[2] == "10.48550/arxiv.1706.03762"
    assert row[3] == "Natural Language Processing Techniques"
    assert row[4] == "transformer; self-attention"
    assert row[5] == pytest.approx(0.823)
    assert row[8] is None  # Otras notas, vacia
    assert ws["C2"].hyperlink.target == "https://doi.org/10.48550/arxiv.1706.03762"
    assert ws.freeze_panes == "A2"
    assert ws.auto_filter.ref == "A1:I2"


def test_write_xlsx_without_doi_links_to_openalex(tmp_path):
    out = tmp_path / "rev.xlsx"
    write([_paper(doi=None)], str(out), format="xlsx")
    ws = _read_xlsx(out)
    assert ws["C2"].hyperlink.target.startswith("https://openalex.org/")


def test_write_xlsx_neutralises_formula_injection(tmp_path):
    """Un titulo que venga de la API empezando por '=' no debe ejecutarse como
    formula al abrir el fichero en Excel."""
    out = tmp_path / "rev.xlsx"
    write([_paper(title='=HYPERLINK("http://evil.example","clic")')], str(out), format="xlsx")
    ws = _read_xlsx(out)
    assert ws["A2"].data_type == "s"
    assert ws["A2"].value.startswith("=HYPERLINK")


def test_write_xlsx_escapes_doi_in_link(tmp_path):
    out = tmp_path / "rev.xlsx"
    write([_paper(doi="10.1/a b?x=1#y")], str(out), format="xlsx")
    ws = _read_xlsx(out)
    target = ws["C2"].hyperlink.target
    assert " " not in target and "?" not in target and "#" not in target


def test_write_xlsx_empty_list_still_has_headers(tmp_path):
    out = tmp_path / "rev.xlsx"
    write([], str(out), format="xlsx")
    ws = _read_xlsx(out)
    assert ws.max_row == 1


def test_infer_format_xlsx():
    assert infer_format("revision.xlsx") == "xlsx"


def test_write_xlsx_access_columns(tmp_path):
    out = tmp_path / "rev.xlsx"
    paper = _paper(access_status="open", access_url="https://repo.edu/a.pdf")
    write([paper], str(out), format="xlsx")
    ws = _read_xlsx(out)
    assert ws["G2"].value == "abierto"
    assert ws["H2"].hyperlink.target == "https://repo.edu/a.pdf"


def test_write_xlsx_ignores_unsafe_access_url(tmp_path):
    out = tmp_path / "rev.xlsx"
    write([_paper(access_status="open", access_url="javascript:alert(1)")], str(out), format="xlsx")
    ws = _read_xlsx(out)
    assert ws["H2"].hyperlink is None
