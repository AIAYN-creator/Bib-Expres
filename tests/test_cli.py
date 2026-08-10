import subprocess
import sys

import argparse

import pytest

from bib_expres.cli import _build_parser, _confirm_title_candidate, _parse_doc_types, _parse_modes
from bib_expres.config import ExpansionMode
from bib_expres.models import DiscoveryMode, Paper


def test_version():
    result = subprocess.run(
        [sys.executable, "-m", "bib_expres.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_missing_doi_and_input_fails():
    result = subprocess.run(
        [sys.executable, "-m", "bib_expres.cli"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "--doi o --input" in result.stderr


def _paper(**overrides):
    defaults = dict(
        openalex_id="W1",
        doi="10.1/abc",
        title="A Paper",
        authors=["A. Author"],
        year=2020,
        venue=None,
        concepts=[],
        citation_count=0,
        generation=0,
        discovered_via=DiscoveryMode.ROOT,
    )
    defaults.update(overrides)
    return Paper(**defaults)


class _FakeOpenAlex:
    def __init__(self, results):
        self._results = results

    def search_by_title(self, title, limit=5):
        return self._results[:limit]


def test_confirm_title_candidate_picks_chosen_number(monkeypatch):
    candidates = [_paper(openalex_id="W1"), _paper(openalex_id="W2")]
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")
    result = _confirm_title_candidate("some title", _FakeOpenAlex(candidates))
    assert result.openalex_id == "W2"


def test_confirm_title_candidate_cancels_on_empty_input(monkeypatch):
    candidates = [_paper(openalex_id="W1")]
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    result = _confirm_title_candidate("some title", _FakeOpenAlex(candidates))
    assert result is None


def test_confirm_title_candidate_no_results():
    result = _confirm_title_candidate("some title", _FakeOpenAlex([]))
    assert result is None


def test_parse_modes_default_style():
    assert _parse_modes("references,citations") == {
        ExpansionMode.REFERENCES,
        ExpansionMode.CITATIONS,
    }


def test_parse_modes_strips_whitespace():
    assert _parse_modes(" references , similar ") == {
        ExpansionMode.REFERENCES,
        ExpansionMode.SIMILAR,
    }


def test_parse_modes_rejects_unknown_mode():
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_modes("references,not-a-mode")


def test_parse_modes_rejects_empty():
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_modes("")


def test_parse_doc_types_splits_and_strips():
    assert _parse_doc_types(" article, preprint ") == {"article", "preprint"}


def test_parse_doc_types_empty_string():
    assert _parse_doc_types("") == set()


def test_doc_types_and_open_access_flags_reach_search_config():
    parser = _build_parser()
    args = parser.parse_args(
        ["--doi", "10.1/x", "--doc-types", "article,dataset", "--open-access-only"]
    )
    assert args.doc_types == {"article", "dataset"}
    assert args.open_access_only is True


def test_doc_types_and_open_access_default_to_no_filter():
    parser = _build_parser()
    args = parser.parse_args(["--doi", "10.1/x"])
    assert args.doc_types is None
    assert args.open_access_only is False
