import pytest

from bib_expres.models import DiscoveryMode, Paper
from bib_expres.resolve import DOIResolutionError, resolve_root_paper


class _FakeOpenAlex:
    def __init__(self, paper=None):
        self._paper = paper

    def resolve_doi(self, doi):
        return self._paper


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
