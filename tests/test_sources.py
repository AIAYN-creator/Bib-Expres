import json
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
        if json_data is not None:
            content = json.dumps(json_data).encode()
        self.content = content
        self.headers = headers or {}
        self.chunks_read = 0

    status_code = 200

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self.content), chunk_size):
            self.chunks_read += 1
            yield self.content[i : i + chunk_size]

    def close(self):
        pass


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


def test_source_client_stops_reading_chunked_response_past_limit(tmp_path, monkeypatch):
    """Sin Content-Length (respuesta chunked), el limite se aplica mientras se
    lee, no despues de haber descargado todo a memoria."""
    client = SourceClient(
        base_url="https://example.com", cache=ResponseCache(path=tmp_path / "c.sqlite3")
    )
    fake = _FakeResponse(content=b"x" * (MAX_RESPONSE_BYTES * 3))
    monkeypatch.setattr(client._session, "get", lambda *a, **k: fake)

    with pytest.raises(requests.RequestException):
        client.get("/works")
    total_chunks = (MAX_RESPONSE_BYTES * 3) // (64 * 1024)
    assert fake.chunks_read < total_chunks / 2


def test_source_client_invalid_json_is_request_exception(tmp_path, monkeypatch):
    client = SourceClient(
        base_url="https://example.com", cache=ResponseCache(path=tmp_path / "c.sqlite3")
    )
    monkeypatch.setattr(client._session, "get", lambda *a, **k: _FakeResponse(content=b"<html>"))

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

    def fake_get(url, params=None, timeout=None, stream=False):
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

    def fake_get(url, params=None, timeout=None, stream=False):
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

    def fake_get(url, params=None, timeout=None, stream=False):
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

    def fake_get(url, params=None, timeout=None, stream=False):
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
        def fake_get(url, params=None, timeout=None, stream=False):
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


def test_parse_openalex_work_topic_and_keywords():
    raw = {
        "id": "https://openalex.org/W1",
        "display_name": "X",
        "primary_topic": {"display_name": "Neural Networks and Applications"},
        "keywords": [{"display_name": "deep learning"}, {"display_name": "backpropagation"}, {}],
    }
    paper = parse_openalex_work(raw)
    assert paper.topic == "Neural Networks and Applications"
    assert paper.keywords == ["deep learning", "backpropagation"]


def test_parse_openalex_work_without_topic_or_keywords():
    paper = parse_openalex_work({"id": "https://openalex.org/W1", "display_name": "X"})
    assert paper.topic is None
    assert paper.keywords == []


def test_parse_openalex_work_language():
    paper = parse_openalex_work({"id": "https://openalex.org/W1", "display_name": "X", "language": "es"})
    assert paper.language == "es"
    assert parse_openalex_work({"id": "https://openalex.org/W1", "display_name": "X"}).language is None


def test_parse_openalex_work_publisher_and_oa_link():
    raw = {
        "id": "https://openalex.org/W1",
        "display_name": "X",
        "primary_location": {"source": {
            "host_organization_name": "Cell Press",
            "host_organization_lineage_names": ["Cell Press", "Elsevier BV"],
        }},
        "open_access": {"is_oa": True, "oa_status": "bronze", "oa_url": "http://www.cell.com/a.pdf"},
    }
    paper = parse_openalex_work(raw)
    assert paper.publisher_lineage == ["Cell Press", "Elsevier BV"]
    assert paper.oa_status == "bronze"
    assert paper.oa_url == "http://www.cell.com/a.pdf"


def test_parse_openalex_work_publisher_without_lineage():
    raw = {"id": "https://openalex.org/W1", "display_name": "X",
           "primary_location": {"source": {"host_organization_name": "Wiley"}}}
    assert parse_openalex_work(raw).publisher_lineage == ["Wiley"]
    assert parse_openalex_work({"id": "https://openalex.org/W1", "display_name": "X"}).publisher_lineage == []

# -- limite de peticiones (HTTP 429) ----------------------------------------------


class _StatusResponse(_FakeResponse):
    def __init__(self, status_code, headers=None, json_data=None):
        super().__init__(content=b"{}", headers=headers, json_data=json_data)
        self.status_code = status_code


def _client(tmp_path):
    return SourceClient(base_url="https://api.example.org", cache=ResponseCache(path=tmp_path / "c.sqlite3"))


def test_long_retry_after_raises_rate_limited_without_sleeping(tmp_path, monkeypatch):
    from bib_expres.sources.base import RateLimitedError

    client = _client(tmp_path)
    monkeypatch.setattr(client._session, "get", lambda *a, **k: _StatusResponse(429, {"Retry-After": "37171"}))
    slept = []
    monkeypatch.setattr("bib_expres.sources.base.time.sleep", slept.append)
    with pytest.raises(RateLimitedError) as exc:
        client.get("/works")
    assert slept == []
    assert "unas 10 horas" in str(exc.value)
    assert "api.example.org" in str(exc.value)
    assert not isinstance(exc.value, requests.RequestException)


def test_short_retry_after_waits_and_retries(tmp_path, monkeypatch):
    client = _client(tmp_path)
    responses = iter([_StatusResponse(429, {"Retry-After": "2"}), _StatusResponse(200, json_data={"ok": 1})])
    monkeypatch.setattr(client._session, "get", lambda *a, **k: next(responses))
    slept = []
    monkeypatch.setattr("bib_expres.sources.base.time.sleep", slept.append)
    assert client.get("/works") == {"ok": 1}
    assert slept == [2.0]


def test_persistent_short_429_is_a_regular_network_failure(tmp_path, monkeypatch):
    client = _client(tmp_path)
    monkeypatch.setattr(client._session, "get", lambda *a, **k: _StatusResponse(429))
    monkeypatch.setattr("bib_expres.sources.base.time.sleep", lambda s: None)
    with pytest.raises(requests.RequestException):
        client.get("/works")


def test_retry_after_http_date_in_the_far_future(tmp_path, monkeypatch):
    from bib_expres.sources.base import RateLimitedError

    client = _client(tmp_path)
    monkeypatch.setattr(
        client._session, "get",
        lambda *a, **k: _StatusResponse(429, {"Retry-After": "Wed, 21 Oct 2099 07:28:00 GMT"}),
    )
    with pytest.raises(RateLimitedError):
        client.get("/works")


def test_session_retry_ignores_retry_after_for_server_errors(tmp_path):
    adapter = _client(tmp_path)._session.get_adapter("https://api.example.org")
    assert adapter.max_retries.respect_retry_after_header is False
    assert 429 not in adapter.max_retries.status_forcelist


# -- cuota diaria (cabeceras X-RateLimit) --------------------------------------------


@pytest.fixture
def clean_quota():
    from bib_expres.sources import base

    base._QUOTA.clear()
    yield base
    base._QUOTA.clear()


def test_quota_is_read_from_response_headers(tmp_path, monkeypatch, clean_quota):
    client = _client(tmp_path)
    headers = {"X-RateLimit-Remaining": "592", "X-RateLimit-Limit": "1000", "X-RateLimit-Reset": "3600"}
    monkeypatch.setattr(client._session, "get", lambda *a, **k: _StatusResponse(200, headers, json_data={"ok": 1}))
    client.get("/works")
    q = clean_quota.quota_status("api.example.org")
    assert q["remaining"] == 592 and q["limit"] == 1000
    assert 3590 < q["reset_in"] <= 3600


def test_quota_unknown_until_a_real_request(clean_quota):
    assert clean_quota.quota_status("api.openalex.org") is None


def test_quota_exhausted_on_long_429(tmp_path, monkeypatch, clean_quota):
    from bib_expres.sources.base import RateLimitedError

    client = _client(tmp_path)
    monkeypatch.setattr(client._session, "get", lambda *a, **k: _StatusResponse(429, {"Retry-After": "7200", "X-RateLimit-Limit": "1000"}))
    with pytest.raises(RateLimitedError):
        client.get("/works")
    q = clean_quota.quota_status("api.example.org")
    assert q["remaining"] == 0 and q["limit"] == 1000 and q["reset_in"] > 7000


def test_quota_refills_after_reset(clean_quota, monkeypatch):
    clean_quota.record_quota("h", {"X-RateLimit-Remaining": "0", "X-RateLimit-Limit": "1000", "X-RateLimit-Reset": "10"})
    real = clean_quota.time.monotonic
    monkeypatch.setattr(clean_quota.time, "monotonic", lambda: real() + 20)
    q = clean_quota.quota_status("h")
    assert q["reset_in"] == 0 and q["remaining"] == 1000


def test_cached_responses_do_not_touch_quota(tmp_path, monkeypatch, clean_quota):
    client = _client(tmp_path)
    headers = {"X-RateLimit-Remaining": "500", "X-RateLimit-Limit": "1000"}
    monkeypatch.setattr(client._session, "get", lambda *a, **k: _StatusResponse(200, headers, json_data={"ok": 1}))
    client.get("/works")
    monkeypatch.setattr(client._session, "get", lambda *a, **k: pytest.fail("deberia salir de la cache"))
    client.get("/works")
    assert clean_quota.quota_status("api.example.org")["remaining"] == 500
