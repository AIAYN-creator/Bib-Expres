import threading
from urllib.parse import quote, unquote, urlsplit

import pytest
import requests

from bib_expres.models import DiscoveryMode, Paper
from bib_expres.sources.base import MAX_RESPONSE_BYTES, ResponseCache, SourceClient
from bib_expres.sources.crossref import CrossrefClient
from bib_expres.sources.crossref import _parse_work as parse_crossref_work
from bib_expres.sources.openalex import OpenAlexClient
from bib_expres.sources.openalex import _parse_work as parse_openalex_work
from bib_expres.sources.openalex import _reconstruct_abstract
from bib_expres.sources.semantic_scholar import SemanticScholarClient


class _FakeResponse:
    def __init__(self, content: bytes, headers: dict | None = None, json_data: dict | None = None):
        self.content = content
        self.headers = headers or {}
        self._json_data = json_data if json_data is not None else {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


def test_parse_openalex_work():
    raw = {
        "id": "https://openalex.org/W123",
        "doi": "https://doi.org/10.1/abc",
        "display_name": "A Paper",
        "authorships": [{"author": {"display_name": "Jane Smith"}}],
        "publication_year": 2020,
        "primary_location": {"source": {"display_name": "A Journal"}},
        "concepts": [{"display_name": "Machine learning", "score": 0.8}],
        "cited_by_count": 15,
        "type": "article",
        "open_access": {"is_oa": True, "oa_status": "gold"},
        "abstract_inverted_index": {"A": [0], "great": [1], "paper": [2]},
    }
    paper = parse_openalex_work(raw)
    assert paper.openalex_id == "W123"
    assert paper.doi == "10.1/abc"
    assert paper.title == "A Paper"
    assert paper.authors == ["Jane Smith"]
    assert paper.year == 2020
    assert paper.venue == "A Journal"
    assert paper.concepts[0].name == "Machine learning"
    assert paper.citation_count == 15
    assert paper.discovered_via == DiscoveryMode.ROOT
    assert paper.doc_type == "article"
    assert paper.open_access is True
    assert paper.abstract == "A great paper"


def test_parse_openalex_work_without_type_or_open_access():
    raw = {"id": "https://openalex.org/W123", "display_name": "A Paper"}
    paper = parse_openalex_work(raw)
    assert paper.doc_type is None
    assert paper.open_access is None
    assert paper.abstract is None


def test_reconstruct_abstract_repeated_word():
    # "the" aparece dos veces, en posiciones distintas
    index = {"the": [0, 3], "cat": [1], "sat": [2], "mat": [4]}
    assert _reconstruct_abstract(index) == "the cat sat the mat"


def test_reconstruct_abstract_none_when_missing():
    assert _reconstruct_abstract(None) is None
    assert _reconstruct_abstract({}) is None


def test_parse_crossref_work():
    raw = {
        "DOI": "10.1/xyz",
        "title": ["Another Paper"],
        "author": [{"given": "John", "family": "Doe"}],
        "published": {"date-parts": [[2019]]},
        "container-title": ["Some Journal"],
        "is-referenced-by-count": 3,
    }
    paper = parse_crossref_work(raw)
    assert paper.doi == "10.1/xyz"
    assert paper.title == "Another Paper"
    assert paper.authors == ["John Doe"]
    assert paper.year == 2019
    assert paper.venue == "Some Journal"
    assert paper.citation_count == 3


def test_response_cache_roundtrip(tmp_path):
    cache = ResponseCache(path=tmp_path / "cache.sqlite3")
    assert cache.get("https://example.com", {"a": 1}) is None
    cache.set("https://example.com", {"a": 1}, {"result": 42})
    assert cache.get("https://example.com", {"a": 1}) == {"result": 42}


def test_response_cache_expires(tmp_path):
    cache = ResponseCache(path=tmp_path / "cache.sqlite3", ttl_seconds=0)
    cache.set("https://example.com", None, {"result": 42})
    assert cache.get("https://example.com", None) is None


def test_response_cache_usable_from_multiple_threads(tmp_path):
    # regresion: pywebview despacha cada llamada de la GUI en un hilo nuevo: una
    # ResponseCache creada en un hilo y usada desde otro reventaba con
    # "SQLite objects created in a thread can only be used in that same thread".
    cache = ResponseCache(path=tmp_path / "cache.sqlite3")
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            url = f"https://example.com/{i}"
            cache.set(url, None, {"result": i})
            assert cache.get(url, None) == {"result": i}
        except BaseException as exc:  # noqa: BLE001 -- se recoge para reportar, no se traga
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors


def test_parse_openalex_work_missing_id_raises():
    with pytest.raises(ValueError, match="sin 'id'"):
        parse_openalex_work({"display_name": "No ID Paper"})


def test_source_client_rejects_oversized_response_by_content_length(tmp_path, monkeypatch):
    client = SourceClient(
        base_url="https://example.com", cache=ResponseCache(path=tmp_path / "c.sqlite3")
    )
    fake = _FakeResponse(content=b"{}", headers={"Content-Length": str(MAX_RESPONSE_BYTES + 1)})
    monkeypatch.setattr(client._session, "get", lambda *a, **k: fake)

    with pytest.raises(requests.RequestException):
        client.get("/works")


def test_source_client_rejects_oversized_response_by_actual_size(tmp_path, monkeypatch):
    client = SourceClient(
        base_url="https://example.com", cache=ResponseCache(path=tmp_path / "c.sqlite3")
    )
    fake = _FakeResponse(content=b"x" * (MAX_RESPONSE_BYTES + 1))
    monkeypatch.setattr(client._session, "get", lambda *a, **k: fake)

    with pytest.raises(requests.RequestException):
        client.get("/works")


def test_semantic_scholar_get_similar_without_doi_returns_empty():
    client = SemanticScholarClient()
    paper = Paper(
        openalex_id="W1",
        doi=None,
        title="No DOI",
        authors=[],
        year=None,
        venue=None,
        concepts=[],
        citation_count=0,
        generation=0,
        discovered_via=DiscoveryMode.ROOT,
    )
    assert client.get_similar(paper, generation=1) == []


# -- seguridad: un DOI con "/" no debe poder anadir segmentos al path -------
#
# _DOI_PATTERN (resolve.py) admite "/", ".", ":", ";", "(", ")" -- caracteres
# que tambien delimitan un path HTTP -- asi que un DOI interpolado sin
# encodear puede alterar la ruta real enviada a la API. Estos tests
# construyen el cliente real (con su SourceClient real) y solo sustituyen
# session.get para capturar la URL final tal como se enviaria a la API.

# DOI valido segun _DOI_PATTERN que, sin encodear, anadiria segmentos "..".
_PATH_INJECTING_DOI = "10.1000/xyz/../../admin"


def test_openalex_resolve_doi_url_encodes_doi_path_characters(tmp_path, monkeypatch):
    client = OpenAlexClient(cache=ResponseCache(path=tmp_path / "c.sqlite3"))
    captured: dict[str, str] = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        return _FakeResponse(
            content=b"{}",
            json_data={"id": "https://openalex.org/W1", "display_name": "X"},
        )

    monkeypatch.setattr(client._client._session, "get", fake_get)

    client.resolve_doi(_PATH_INJECTING_DOI)

    path = urlsplit(captured["url"]).path
    expected_prefix = "/works/doi:"
    assert path == expected_prefix + quote(_PATH_INJECTING_DOI, safe="")
    assert path.count("/") == expected_prefix.count("/")  # sin segmentos extra
    assert unquote(path.removeprefix(expected_prefix)) == _PATH_INJECTING_DOI


# openalex_id valido en forma (lo que produce _strip_openalex_id) pero que,
# sin encodear, anadiria segmentos "..". Mismo patron que _PATH_INJECTING_DOI,
# solo que este campo lo rellena el propio OpenAlex en una respuesta previa,
# no una fuente externa -- por eso el riesgo es menor, pero la construccion
# del path es identica y merece la misma proteccion.
_PATH_INJECTING_OPENALEX_ID = "W123/../../admin"


def test_openalex_get_references_url_encodes_openalex_id_path_characters(
    tmp_path, monkeypatch
):
    client = OpenAlexClient(cache=ResponseCache(path=tmp_path / "c.sqlite3"))
    captured: dict[str, str] = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        return _FakeResponse(content=b"{}", json_data={"referenced_works": []})

    monkeypatch.setattr(client._client._session, "get", fake_get)

    paper = Paper(
        openalex_id=_PATH_INJECTING_OPENALEX_ID,
        doi=None,
        title="Root",
        authors=[],
        year=None,
        venue=None,
        concepts=[],
        citation_count=0,
        generation=0,
        discovered_via=DiscoveryMode.ROOT,
    )
    client.get_references(paper, generation=1)

    path = urlsplit(captured["url"]).path
    expected_prefix = "/works/"
    assert path == expected_prefix + quote(_PATH_INJECTING_OPENALEX_ID, safe="")
    assert path.count("/") == expected_prefix.count("/")  # sin segmentos extra
    assert unquote(path.removeprefix(expected_prefix)) == _PATH_INJECTING_OPENALEX_ID


def test_crossref_resolve_doi_url_encodes_doi_path_characters(tmp_path, monkeypatch):
    client = CrossrefClient(cache=ResponseCache(path=tmp_path / "c.sqlite3"))
    captured: dict[str, str] = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        return _FakeResponse(content=b"{}")

    monkeypatch.setattr(client._client._session, "get", fake_get)

    client.resolve_doi(_PATH_INJECTING_DOI)

    path = urlsplit(captured["url"]).path
    expected_prefix = "/works/"
    assert path == expected_prefix + quote(_PATH_INJECTING_DOI, safe="")
    assert path.count("/") == expected_prefix.count("/")  # sin segmentos extra
    assert unquote(path.removeprefix(expected_prefix)) == _PATH_INJECTING_DOI


def test_semantic_scholar_get_similar_url_encodes_paper_doi(tmp_path, monkeypatch):
    client = SemanticScholarClient(cache=ResponseCache(path=tmp_path / "c.sqlite3"))
    captured: dict[str, str] = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        return _FakeResponse(content=b"{}", json_data={"recommendedPapers": []})

    monkeypatch.setattr(client._client._session, "get", fake_get)

    paper = Paper(
        openalex_id="W0",
        doi=_PATH_INJECTING_DOI,
        title="Root",
        authors=[],
        year=None,
        venue=None,
        concepts=[],
        citation_count=0,
        generation=0,
        discovered_via=DiscoveryMode.ROOT,
    )
    client.get_similar(paper, generation=1)

    path = urlsplit(captured["url"]).path
    expected_prefix = "/recommendations/v1/papers/forpaper/DOI:"
    assert path == expected_prefix + quote(_PATH_INJECTING_DOI, safe="")
    assert unquote(path.removeprefix(expected_prefix)) == _PATH_INJECTING_DOI


def test_semantic_scholar_get_similar_encodes_untrusted_candidate_doi_from_api(
    tmp_path, monkeypatch
):
    # El caso mas grave: candidate_doi no pasa por _DOI_PATTERN -- viene tal
    # cual de la respuesta JSON de Semantic Scholar (fuente externa) y se usa
    # directo para resolver via OpenAlex. Debe quedar igual de bien
    # encodeado que un DOI que si paso por la validacion local.
    cache = ResponseCache(path=tmp_path / "c.sqlite3")
    client = SemanticScholarClient(cache=cache)
    captured_urls: list[str] = []

    def make_fake_get(json_data):
        def fake_get(url, params=None, timeout=None):
            captured_urls.append(url)
            return _FakeResponse(content=b"{}", json_data=json_data)

        return fake_get

    monkeypatch.setattr(
        client._client._session,
        "get",
        make_fake_get(
            {"recommendedPapers": [{"externalIds": {"DOI": _PATH_INJECTING_DOI}}]}
        ),
    )
    monkeypatch.setattr(
        client._openalex._client._session,
        "get",
        make_fake_get({"id": "https://openalex.org/W1", "display_name": "X"}),
    )

    paper = Paper(
        openalex_id="W0",
        doi="10.1/root",
        title="Root",
        authors=[],
        year=None,
        venue=None,
        concepts=[],
        citation_count=0,
        generation=0,
        discovered_via=DiscoveryMode.ROOT,
    )
    client.get_similar(paper, generation=1)

    assert len(captured_urls) == 2
    candidate_resolution_path = urlsplit(captured_urls[1]).path
    assert candidate_resolution_path == "/works/doi:" + quote(_PATH_INJECTING_DOI, safe="")
