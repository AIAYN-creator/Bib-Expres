import subprocess
import sys

import argparse

import pytest

from bib_expres.cli import _parse_modes
from bib_expres.config import ExpansionMode


def test_version():
    result = subprocess.run(
        [sys.executable, "-m", "bib_expres.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_missing_doi_fails():
    result = subprocess.run(
        [sys.executable, "-m", "bib_expres.cli"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


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
