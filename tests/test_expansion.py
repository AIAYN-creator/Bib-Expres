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


def test_expand_fanout_limits_exploration_not_results():
    """v3: de cada paper solo se exploran los `fanout` candidatos mas relevantes,
    pero todos los vistos pueden acabar en el resultado."""
    root = _paper("root", concepts=[Concept(name="Cats", score=1.0)])
    relevant = _paper("relevant", concepts=[Concept(name="Cats", score=1.0)])
    irrelevant = _paper("irrelevant", concepts=[Concept(name="Dogs", score=1.0)])
    behind_irrelevant = _paper("behind", concepts=[Concept(name="Cats", score=1.0)])
    behind_relevant = _paper("child", concepts=[Concept(name="Cats", score=1.0)])
    openalex = _FakeOpenAlex(
        references={
            "root": [irrelevant, relevant],
            "relevant": [behind_relevant],
            "irrelevant": [behind_irrelevant],
        }
    )

    config = SearchConfig(
        generations=2,
        max_articles=10,
        max_fanout_per_node=1,
        relevance_threshold=0.0,
        modes={ExpansionMode.REFERENCES},
    )
    ids = {p.openalex_id for p in expand(root, config, openalex_client=openalex)}
    assert {"relevant", "irrelevant", "child"} <= ids
    assert "behind" not in ids  # "irrelevant" no se exploro: fuera del fanout

def test_expand_reports_progress_and_finishes():
    root = _paper("root")
    refs = [_paper(f"r{i}") for i in range(3)]
    openalex = _FakeOpenAlex(references={"root": refs})
    events = []

    config = SearchConfig(generations=1, max_articles=10, modes={ExpansionMode.REFERENCES})
    expand(root, config, openalex_client=openalex, on_progress=events.append)

    assert events[0].current_title == "Paper root"
    assert events[0].explored == 0 and events[0].planned == 1
    last = events[-1]
    assert last.finished and not last.cancelled
    assert last.explored == 1
    assert last.candidates == 3


def test_expand_progress_explored_never_decreases():
    root = _paper("root")
    gen1 = [_paper(f"a{i}") for i in range(3)]
    gen2 = {f"a{i}": [_paper(f"b{i}{j}") for j in range(2)] for i in range(3)}
    openalex = _FakeOpenAlex(references={"root": gen1, **gen2})
    events = []

    config = SearchConfig(generations=2, max_articles=50, modes={ExpansionMode.REFERENCES})
    expand(root, config, openalex_client=openalex, on_progress=events.append)

    explored = [e.explored for e in events]
    assert explored == sorted(explored)
    assert events[-1].explored == 4  # el padre + sus 3 referencias
    assert {e.generation for e in events if not e.finished} == {1, 2}


def test_expand_cancel_returns_partial_results():
    root = _paper("root")
    gen1 = [_paper(f"a{i}") for i in range(3)]
    gen2 = {f"a{i}": [_paper(f"b{i}{j}") for j in range(2)] for i in range(3)}
    openalex = _FakeOpenAlex(references={"root": gen1, **gen2})
    events = []
    calls = {"n": 0}

    def cancel_after_first_node():
        calls["n"] += 1
        return calls["n"] > 1

    config = SearchConfig(generations=2, max_articles=50, modes={ExpansionMode.REFERENCES})
    result = expand(
        root,
        config,
        openalex_client=openalex,
        on_progress=events.append,
        should_cancel=cancel_after_first_node,
    )

    assert {p.openalex_id for p in result} == {"root", "a0", "a1", "a2"}
    assert events[-1].finished and events[-1].cancelled


def test_expand_without_callbacks_still_works():
    root = _paper("root")
    openalex = _FakeOpenAlex(references={"root": [_paper("x")]})
    config = SearchConfig(generations=1, max_articles=10, modes={ExpansionMode.REFERENCES})
    assert len(expand(root, config, openalex_client=openalex)) == 2


# -- filtro por idioma ---------------------------------------------------------


def _lang_graph():
    root = _paper("root", language="es")
    es = _paper("es1", language="es")
    en = _paper("en1", language="en")
    unknown = _paper("xx1", language=None)
    return root, _FakeOpenAlex(references={"root": [es, en, unknown]})


def test_expand_any_language_by_default():
    root, openalex = _lang_graph()
    config = SearchConfig(generations=1, max_articles=10, modes={ExpansionMode.REFERENCES})
    ids = {p.openalex_id for p in expand(root, config, openalex_client=openalex)}
    assert ids == {"root", "es1", "en1", "xx1"}


def test_expand_same_language_as_root_keeps_unknown():
    root, openalex = _lang_graph()
    config = SearchConfig(
        generations=1, max_articles=10, modes={ExpansionMode.REFERENCES}, same_language_as_root=True
    )
    ids = {p.openalex_id for p in expand(root, config, openalex_client=openalex)}
    assert ids == {"root", "es1", "xx1"}


def test_expand_same_language_with_unknown_root_language_does_not_filter():
    _, openalex = _lang_graph()
    root = _paper("root", language=None)
    config = SearchConfig(
        generations=1, max_articles=10, modes={ExpansionMode.REFERENCES}, same_language_as_root=True
    )
    assert len(expand(root, config, openalex_client=openalex)) == 4


def test_expand_explicit_languages():
    root, openalex = _lang_graph()
    config = SearchConfig(
        generations=1, max_articles=10, modes={ExpansionMode.REFERENCES}, languages={"EN "}
    )
    ids = {p.openalex_id for p in expand(root, config, openalex_client=openalex)}
    assert ids == {"root", "en1", "xx1"}  # el padre nunca se descarta


def test_search_config_empty_languages_means_no_filter():
    assert SearchConfig(languages={" ", ""}).languages is None


# -- v3: pool, conexiones, presupuesto y desglose ---------------------------------


def test_expand_ranks_connected_papers_higher():
    """Un paper que aparece en varios de los papers explorados sube por conexiones."""
    root = _paper("root")
    a, b = _paper("a"), _paper("b")
    hub = _paper("hub")
    loner = _paper("loner")
    openalex = _FakeOpenAlex(references={"root": [a, b, loner], "a": [hub], "b": [hub]})
    config = SearchConfig(generations=2, max_articles=50, modes={ExpansionMode.REFERENCES})
    result = expand(root, config, openalex_client=openalex)
    by_id = {p.openalex_id: p for p in result}
    assert by_id["hub"].score_breakdown["conexiones"] == 2
    assert by_id["loner"].score_breakdown["conexiones"] == 1
    assert by_id["hub"].relevance_score > by_id["loner"].relevance_score


def test_expand_returns_best_first_and_respects_cap():
    root = _paper("root")
    refs = [_paper(f"r{i}", citation_count=i * 100) for i in range(10)]
    openalex = _FakeOpenAlex(references={"root": refs})
    config = SearchConfig(generations=1, max_articles=4, modes={ExpansionMode.REFERENCES})
    result = expand(root, config, openalex_client=openalex)
    assert result[0] is root and len(result) == 4
    scores = [p.relevance_score for p in result[1:]]
    assert scores == sorted(scores, reverse=True)


def test_expand_explore_budget_limits_expansions():
    root = _paper("root")
    gen1 = [_paper(f"a{i}") for i in range(5)]
    gen2 = {f"a{i}": [_paper(f"b{i}")] for i in range(5)}
    openalex = _FakeOpenAlex(references={"root": gen1, **gen2})
    events = []
    config = SearchConfig(
        generations=2, max_articles=50, explore_budget=3, modes={ExpansionMode.REFERENCES}
    )
    expand(root, config, openalex_client=openalex, on_progress=events.append)
    assert events[-1].explored == 3
    assert events[-1].planned == 3


def test_filters_do_not_cut_exploration():
    """v3: un paper filtrado (p.ej. por idioma) sigue llevando a otros que si pasan."""
    root = _paper("root", language="es")
    bridge = _paper("bridge", language="en")
    target = _paper("target", language="es")
    openalex = _FakeOpenAlex(references={"root": [bridge], "bridge": [target]})
    config = SearchConfig(
        generations=2, max_articles=50, modes={ExpansionMode.REFERENCES}, same_language_as_root=True
    )
    ids = {p.openalex_id for p in expand(root, config, openalex_client=openalex)}
    assert "target" in ids and "bridge" not in ids


def test_score_breakdown_and_explain():
    from bib_expres.relevance import explain

    root = _paper("root", keywords=["transformer", "attention"])
    child = _paper("c", keywords=["Attention", "vision"])
    openalex = _FakeOpenAlex(references={"root": [child]})
    config = SearchConfig(generations=1, max_articles=10, modes={ExpansionMode.REFERENCES})
    result = expand(root, config, openalex_client=openalex)
    bd = result[1].score_breakdown
    assert bd["palabras_clave"] == ["attention"]
    assert bd["final"] == result[1].relevance_score
    text = explain(bd)
    assert text.startswith(f"{bd['final']:.2f} = relevancia")
    assert "comparte: attention" in text


def test_planned_expansions():
    from bib_expres.expansion import planned_expansions

    assert planned_expansions(SearchConfig(generations=1)) == 1
    assert planned_expansions(SearchConfig(generations=2, max_fanout_per_node=20)) == 21
    assert planned_expansions(SearchConfig(generations=3, max_fanout_per_node=20)) == 30
