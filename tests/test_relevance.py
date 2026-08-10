from bib_expres.config import RelevanceWeights
from bib_expres.models import Concept, DiscoveryMode, Paper
from bib_expres.relevance import dedup_key, deduplicate, meets_threshold, score


def _paper(**overrides):
    defaults = dict(
        openalex_id="W1",
        doi="10.1/a",
        title="A Paper About Cats",
        authors=["Ana Autora"],
        year=2020,
        venue="Journal",
        concepts=[Concept(name="Cats", score=0.9)],
        citation_count=10,
        generation=1,
        discovered_via=DiscoveryMode.REFERENCE,
    )
    defaults.update(overrides)
    return Paper(**defaults)


def test_score_is_bounded_and_rewards_topic_overlap():
    parent = _paper(concepts=[Concept(name="Cats", score=1.0)])
    same_topic = _paper(concepts=[Concept(name="Cats", score=1.0)])
    different_topic = _paper(concepts=[Concept(name="Dogs", score=1.0)])

    weights = RelevanceWeights()
    score_same = score(same_topic, parent, weights, current_year=2024)
    score_different = score(different_topic, parent, weights, current_year=2024)

    assert 0.0 <= score_same <= 1.0
    assert 0.0 <= score_different <= 1.0
    assert score_same > score_different


def test_dedup_key_prefers_doi():
    a = _paper(doi="10.1/SAME")
    b = _paper(doi="10.1/same", title="Different title entirely")
    assert dedup_key(a) == dedup_key(b)


def test_dedup_key_falls_back_to_title_author_year_without_doi():
    a = _paper(doi=None, title="A Paper About Cats", authors=["Ana Autora"], year=2020)
    b = _paper(doi=None, title="a paper about cats!!", authors=["ana autora"], year=2020)
    assert dedup_key(a) == dedup_key(b)


def test_deduplicate_keeps_highest_scoring_duplicate():
    low = _paper(doi="10.1/x")
    low.relevance_score = 0.2
    high = _paper(doi="10.1/x", title="different title, same doi")
    high.relevance_score = 0.8

    result = deduplicate([low, high])
    assert len(result) == 1
    assert result[0].relevance_score == 0.8


def test_meets_threshold():
    p = _paper()
    p.relevance_score = 0.5
    assert meets_threshold(p, 0.3)
    assert not meets_threshold(p, 0.6)
