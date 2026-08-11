import pytest

from bib_expres.models import DiscoveryMode, Paper
from bib_expres.resolve import (
    DOIResolutionError,
    TitleSearchRequired,
    extract_from_pdf,
    normalize_arxiv_to_doi,
    resolve_input,
    resolve_root_paper,
    search_by_title,
)


class _FakeOpenAlex:
    def __init__(self, paper=None, search_results=None):
        self._paper = paper
        self._search_results = search_results or []

    def resolve_doi(self, doi):
        return self._paper

    def search_by_title(self, title, limit=5):
        return self._search_results[:limit]


class _FakeCrossref:
    def __init__(self, paper=None):
        self._paper = paper

    def resolve_doi(self, doi):
        return self._paper


def _paper(**overrides):
    defaults = dict(
        openalex_id="W1",
        doi="10.1/abc",
        title="A Paper",
        authors=["A"],
        year=2020,
        venue=None,
        concepts=[],
        citation_count=0,
        generation=0,
        discovered_via=DiscoveryMode.ROOT,
    )
    defaults.update(overrides)
    return Paper(**defaults)


def test_resolve_uses_openalex_when_available():
    result = resolve_root_paper(
        "10.1/abc",
        openalex_client=_FakeOpenAlex(_paper()),
        crossref_client=_FakeCrossref(),
    )
    assert result.openalex_id == "W1"


def test_resolve_raises_when_doi_unknown_everywhere():
    with pytest.raises(DOIResolutionError, match="No se ha encontrado"):
        resolve_root_paper(
            "10.1/nope",
            openalex_client=_FakeOpenAlex(None),
            crossref_client=_FakeCrossref(None),
        )


def test_resolve_raises_specific_error_when_only_crossref_has_it():
    with pytest.raises(DOIResolutionError, match="todavia no esta indexado en OpenAlex"):
        resolve_root_paper(
            "10.1/new",
            openalex_client=_FakeOpenAlex(None),
            crossref_client=_FakeCrossref(_paper()),
        )


# -- normalize_arxiv_to_doi -----------------------------------------------


def test_normalize_arxiv_new_style_bare_id():
    assert normalize_arxiv_to_doi("2301.12345") == "10.48550/arXiv.2301.12345"


def test_normalize_arxiv_strips_version_suffix():
    assert normalize_arxiv_to_doi("2301.12345v2") == "10.48550/arXiv.2301.12345"


def test_normalize_arxiv_abs_url():
    assert (
        normalize_arxiv_to_doi("https://arxiv.org/abs/2301.12345")
        == "10.48550/arXiv.2301.12345"
    )


def test_normalize_arxiv_pdf_url():
    assert (
        normalize_arxiv_to_doi("https://arxiv.org/pdf/2301.12345.pdf")
        == "10.48550/arXiv.2301.12345"
    )


def test_normalize_arxiv_old_style_id():
    assert normalize_arxiv_to_doi("math/0211159") == "10.48550/arXiv.math/0211159"


def test_normalize_arxiv_rejects_non_arxiv_input():
    assert normalize_arxiv_to_doi("this is just a title") is None
    assert normalize_arxiv_to_doi("10.1000/abc123") is None


# -- resolve_input ----------------------------------------------------------


def test_resolve_input_doi_passthrough():
    result = resolve_input(
        "10.1/abc", openalex_client=_FakeOpenAlex(_paper()), crossref_client=_FakeCrossref()
    )
    assert result.openalex_id == "W1"


def test_resolve_input_arxiv_resolves_via_constructed_doi():
    result = resolve_input(
        "2301.12345",
        openalex_client=_FakeOpenAlex(_paper()),
        crossref_client=_FakeCrossref(),
    )
    assert result.openalex_id == "W1"


def test_resolve_input_arxiv_unresolved_gives_actionable_message():
    # hallazgo real en validacion-e2e-v2: el DOI de arXiv es valido pero
    # OpenAlex/CrossRef solo indexan por DOI *principal* -- si el paper se
    # publico despues en otro sitio con su propio DOI, esta busqueda falla
    # aunque el DOI de arXiv exista de verdad. El mensaje debe explicar esto,
    # no limitarse a repetir "DOI no encontrado" como si el usuario hubiera
    # escrito un DOI a mano.
    with pytest.raises(DOIResolutionError, match="Prueba a buscarlo por su titulo"):
        resolve_input(
            "1706.03762",
            openalex_client=_FakeOpenAlex(None),
            crossref_client=_FakeCrossref(None),
        )


def test_resolve_input_plain_doi_unresolved_keeps_generic_message():
    # el mismo fallo con un DOI tecleado a mano no debe mencionar arXiv
    with pytest.raises(DOIResolutionError) as exc_info:
        resolve_input(
            "10.1/nope",
            openalex_client=_FakeOpenAlex(None),
            crossref_client=_FakeCrossref(None),
        )
    assert "arXiv" not in str(exc_info.value)


def test_resolve_input_free_text_raises_title_search_required():
    with pytest.raises(TitleSearchRequired) as exc_info:
        resolve_input("Attention Is All You Need")
    assert exc_info.value.query == "Attention Is All You Need"


def test_resolve_input_pdf_with_doi(tmp_path, monkeypatch):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"not a real pdf, extract_from_pdf is mocked below")
    monkeypatch.setattr(
        "bib_expres.resolve.extract_from_pdf", lambda path: ("10.1/abc", None)
    )

    result = resolve_input(
        str(pdf_path), openalex_client=_FakeOpenAlex(_paper()), crossref_client=_FakeCrossref()
    )
    assert result.openalex_id == "W1"


def test_resolve_input_pdf_without_doi_raises_title_search_required(tmp_path, monkeypatch):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"not a real pdf, extract_from_pdf is mocked below")
    monkeypatch.setattr(
        "bib_expres.resolve.extract_from_pdf", lambda path: (None, "Guessed Title")
    )

    with pytest.raises(TitleSearchRequired) as exc_info:
        resolve_input(str(pdf_path))
    assert exc_info.value.query == "Guessed Title"


def test_resolve_input_nonexistent_pdf_path_falls_back_to_title_search():
    # no existe en disco -> no se trata como PDF, se trata como texto libre
    with pytest.raises(TitleSearchRequired):
        resolve_input("C:/no/existe/paper.pdf")


# -- search_by_title ----------------------------------------------------------


def test_search_by_title_delegates_to_openalex_client():
    candidates = [_paper(openalex_id="W1"), _paper(openalex_id="W2")]
    openalex = _FakeOpenAlex(search_results=candidates)
    result = search_by_title("some title", openalex)
    assert [p.openalex_id for p in result] == ["W1", "W2"]


# -- extract_from_pdf ---------------------------------------------------------


class _FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class _FakeReader:
    def __init__(self, pages):
        self.pages = pages


def test_extract_from_pdf_finds_doi(monkeypatch):
    text = "Journal of Examples\nSome Title Here\nDOI: 10.1000/xyz123\n"
    monkeypatch.setattr(
        "bib_expres.resolve.PdfReader", lambda path: _FakeReader([_FakePage(text)])
    )
    doi, title = extract_from_pdf("whatever.pdf")
    assert doi == "10.1000/xyz123"
    assert title is None


def test_extract_from_pdf_falls_back_to_title_guess(monkeypatch):
    text = "short\nThis Is Probably The Real Title Of The Paper\nx\n"
    monkeypatch.setattr(
        "bib_expres.resolve.PdfReader", lambda path: _FakeReader([_FakePage(text)])
    )
    doi, title = extract_from_pdf("whatever.pdf")
    assert doi is None
    assert title == "This Is Probably The Real Title Of The Paper"


def test_extract_from_pdf_missing_file_returns_none_none(tmp_path):
    missing = tmp_path / "does-not-exist.pdf"
    assert extract_from_pdf(str(missing)) == (None, None)
