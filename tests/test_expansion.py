import dataclasses

from bib_expres.config import ExpansionMode, SearchConfig
from bib_expres.expansion import expand
from bib_expres.models import Concept, DiscoveryMode, Paper


def _paper(id_, **overrides):
    defaults = dict(
        openalex_id=id_,
        doi=f"10.1/{id_}",
        title=f"Paper {id_}",
        authors=["A"],
        year=2020,
        venue=None,
        concepts=[Concept(name="Topic", score=1.0)],
        citation_count=1,
        generation=0,
        discovered_via=DiscoveryMode.ROOT,
    )
    defaults.update(overrides)
    return Paper(**defaults)


class _FakeOpenAlex:
    def __init__(self, references=None):
        self._references = references or {}

    def get_references(self, paper, generation):
        return [
            dataclasses.replace(p, generation=generation, discovered_via=DiscoveryMode.REFERENCE)
            for p in self._references.get(paper.openalex_id, [])
        ]

    def get_citations(self, paper, generation):
        return []


def test_expand_respects_generation_limit():
    root = _paper("root")
    gen1 = _paper("gen1")
    gen2 = _paper("gen2")
    openalex = _FakeOpenAlex(references={"root": [gen1], "gen1": [gen2]})

    config = SearchConfig(generations=1, max_articles=10, modes={ExpansionMode.REFERENCES})
    result = expand(root, config, openalex_client=openalex)

    ids = {p.openalex_id for p in result}
    assert ids == {"root", "gen1"}


def test_expand_respects_total_article_cap():
    root = _paper("root")
    refs = [_paper(f"r{i}") for i in range(10)]
    openalex = _FakeOpenAlex(references={"root": refs})

    config = SearchConfig(generations=2, max_articles=4, modes={ExpansionMode.REFERENCES})
    result = expand(root, config, openalex_client=openalex)

    assert len(result) == 4


def test_expand_deduplicates_across_paths():
    root = _paper("root")
    shared = _paper("shared")
    a = _paper("a")
    openalex = _FakeOpenAlex(references={"root": [a, shared], "a": [shared]})

    config = SearchConfig(generations=2, max_articles=10, modes={ExpansionMode.REFERENCES})
    result = expand(root, config, openalex_client=openalex)

    shared_count = sum(1 for p in result if p.openalex_id == "shared")
    assert shared_count == 1


def test_expand_filters_by_doc_type():
    root = _paper("root")
    article = _paper("article", doc_type="article")
    dataset = _paper("dataset", doc_type="dataset")
    openalex = _FakeOpenAlex(references={"root": [article, dataset]})

    config = SearchConfig(
        generations=1,
        max_articles=10,
        relevance_threshold=0.0,
        allowed_doc_types={"article"},
        modes={ExpansionMode.REFERENCES},
    )
    result = expand(root, config, openalex_client=openalex)

    ids = {p.openalex_id for p in result}
    assert "article" in ids
    assert "dataset" not in ids


def test_expand_filters_by_open_access():
    root = _paper("root")
    oa = _paper("oa", open_access=True)
    closed = _paper("closed", open_access=False)
    unknown = _paper("unknown", open_access=None)
    openalex = _FakeOpenAlex(references={"root": [oa, closed, unknown]})

    config = SearchConfig(
        generations=1,
        max_articles=10,
        relevance_threshold=0.0,
        require_open_access=True,
        modes={ExpansionMode.REFERENCES},
    )
    result = expand(root, config, openalex_client=openalex)

    ids = {p.openalex_id for p in result}
    assert ids == {"root", "oa"}


def test_expand_excluded_candidate_does_not_take_fanout_slot_from_valid_one():
    # dataset puntuaria mas alto que article por solapamiento tematico -- si el
    # filtro se aplicara despues de cortar por fanout (en vez de antes), dataset
    # se quedaria con el unico hueco y luego se descartaria, dejando el hueco vacio.
    root = _paper("root", concepts=[Concept(name="Cats", score=1.0)])
    dataset = _paper("dataset", doc_type="dataset", concepts=[Concept(name="Cats", score=1.0)])
    article = _paper("article", doc_type="article", concepts=[Concept(name="Dogs", score=1.0)])
    openalex = _FakeOpenAlex(references={"root": [dataset, article]})

    config = SearchConfig(
        generations=1,
        max_articles=10,
        max_fanout_per_node=1,
        relevance_threshold=0.0,
        allowed_doc_types={"article"},
        modes={ExpansionMode.REFERENCES},
    )
    result = expand(root, config, openalex_client=openalex)

    ids = {p.openalex_id for p in result}
    assert "article" in ids
    assert "dataset" not in ids


def test_expand_prioritises_higher_relevance_within_fanout_cap():
    root = _paper("root", concepts=[Concept(name="Cats", score=1.0)])
    relevant = _paper("relevant", concepts=[Concept(name="Cats", score=1.0)])
    irrelevant = _paper("irrelevant", concepts=[Concept(name="Dogs", score=1.0)])
    openalex = _FakeOpenAlex(references={"root": [irrelevant, relevant]})

    config = SearchConfig(
        generations=1,
        max_articles=10,
        max_fanout_per_node=1,
        relevance_threshold=0.0,
        modes={ExpansionMode.REFERENCES},
    )
    result = expand(root, config, openalex_client=openalex)

    ids = {p.openalex_id for p in result}
    assert "relevant" in ids
    assert "irrelevant" not in ids
