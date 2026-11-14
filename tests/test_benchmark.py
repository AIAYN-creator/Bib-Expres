import json
import sys
from pathlib import Path

import pytest

BENCH_DIR = Path(__file__).resolve().parent.parent / "benchmarks"
sys.path.insert(0, str(BENCH_DIR))

from run_benchmark import precision_at, rank_by_relevance, recall_at  # noqa: E402

from bib_expres.models import DiscoveryMode, Paper  # noqa: E402


def _paper(id_, score):
    return Paper(
        openalex_id=id_, doi=None, title=id_, authors=[], year=2020, venue=None, concepts=[],
        citation_count=0, generation=1, discovered_via=DiscoveryMode.REFERENCE,
        relevance_score=score,
    )


def test_recall_and_precision_at_n():
    ranked = ["a", "b", "c", "d"]
    truth = {"a", "c", "z", "y"}
    assert recall_at(ranked, truth, 2) == pytest.approx(1 / 4)
    assert recall_at(ranked, truth, 4) == pytest.approx(2 / 4)
    assert precision_at(ranked, truth, 2) == pytest.approx(1 / 2)
    assert precision_at(ranked, truth, 10) == pytest.approx(2 / 4)  # solo cuenta lo devuelto


def test_metrics_with_empty_inputs():
    assert recall_at(["a"], set(), 10) == 0.0
    assert precision_at([], {"a"}, 10) == 0.0


def test_rank_by_relevance_sorts_and_excludes():
    papers = [_paper("seed", 1.0), _paper("low", 0.2), _paper("high", 0.9), _paper("review", 0.95)]
    ranked = rank_by_relevance(papers, exclude_ids={"seed", "review"})
    assert [p.openalex_id for p in ranked] == ["high", "low"]


def test_cases_file_is_well_formed():
    cases = json.loads((BENCH_DIR / "cases.json").read_text(encoding="utf-8"))["cases"]
    assert len(cases) >= 3
    required = {"id", "seed_doi", "seed_label", "review_doi", "review_label"}
    for case in cases:
        assert required <= case.keys()
    assert len({c["id"] for c in cases}) == len(cases)
