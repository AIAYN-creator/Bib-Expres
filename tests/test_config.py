import pytest

from bib_expres.config import ExpansionMode, InstallConfig, SearchConfig


def test_search_config_defaults():
    config = SearchConfig()
    assert config.generations == 2
    assert ExpansionMode.REFERENCES in config.modes
    assert ExpansionMode.CITATIONS in config.modes
    assert ExpansionMode.SIMILAR not in config.modes


def test_search_config_rejects_too_many_generations():
    with pytest.raises(ValueError):
        SearchConfig(generations=6)


def test_install_config_from_env(monkeypatch):
    monkeypatch.setenv("CONTACT_EMAIL", "test@example.com")
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    install = InstallConfig.from_env()
    assert install.contact_email == "test@example.com"
    assert install.semantic_scholar_api_key is None
