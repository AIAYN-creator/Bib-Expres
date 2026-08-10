from bib_expres.models import DiscoveryMode, Paper
from bib_expres.sources.base import ResponseCache
from bib_expres.sources.crossref import _parse_work as parse_crossref_work
from bib_expres.sources.openalex import _parse_work as parse_openalex_work
from bib_expres.sources.semantic_scholar import SemanticScholarClient


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
