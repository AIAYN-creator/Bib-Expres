from bib_expres.gui.app import Api, _config_from_params, _paper_to_dict, save_env_settings
from bib_expres.models import DiscoveryMode, Paper


def _paper(**overrides):
    defaults = dict(
        openalex_id="W1",
        doi="10.1/abc",
        title="A Paper",
        authors=["Jane Smith"],
        year=2020,
        venue="A Journal",
        concepts=[],
        citation_count=5,
        generation=0,
        discovered_via=DiscoveryMode.ROOT,
    )
    defaults.update(overrides)
    return Paper(**defaults)


class _FakeOpenAlex:
    def __init__(self, resolve_result=None, search_results=None, references=None, citations=None):
        self._resolve_result = resolve_result
        self._search_results = search_results or []
        self._references = references or []
        self._citations = citations or []

    def resolve_doi(self, doi):
        return self._resolve_result

    def search_by_title(self, title, limit=5):
        return self._search_results[:limit]

    def get_references(self, paper, generation):
        return self._references

    def get_citations(self, paper, generation):
        return self._citations


class _FakeCrossref:
    def resolve_doi(self, doi):
        return None


class _FakeWindow:
    def __init__(self, dialog_result=None):
        self.dialog_result = dialog_result
        self.calls = []

    def create_file_dialog(self, dialog_type, **kwargs):
        self.calls.append((dialog_type, kwargs))
        return self.dialog_result


# -- _paper_to_dict -----------------------------------------------------------


def test_paper_to_dict_roundtrips_fields():
    paper = _paper(doc_type="article", open_access=True, relevance_score=0.5)
    d = _paper_to_dict(paper)
    assert d["title"] == "A Paper"
    assert d["doc_type"] == "article"
    assert d["open_access"] is True
    assert d["relevance_score"] == 0.5


# -- Api.resolve / confirm_candidate ------------------------------------------


def test_api_resolve_doi_success():
    api = Api(
        openalex_client=_FakeOpenAlex(resolve_result=_paper()), crossref_client=_FakeCrossref()
    )
    res = api.resolve("10.1/abc")
    assert res["status"] == "resolved"
    assert res["paper"]["title"] == "A Paper"
    assert api._root is not None


def test_api_resolve_needs_confirmation():
    candidates = [_paper(openalex_id="W1"), _paper(openalex_id="W2")]
    api = Api(
        openalex_client=_FakeOpenAlex(search_results=candidates), crossref_client=_FakeCrossref()
    )
    res = api.resolve("some free text title")
    assert res["status"] == "needs_confirmation"
    assert len(res["candidates"]) == 2
    assert api._candidates == candidates


def test_api_resolve_doi_not_found_error():
    api = Api(
        openalex_client=_FakeOpenAlex(resolve_result=None), crossref_client=_FakeCrossref()
    )
    res = api.resolve("10.1/nope")
    assert res["status"] == "error"
    assert "No se ha encontrado" in res["message"]


def test_api_confirm_candidate_picks_index():
    candidates = [_paper(openalex_id="W1"), _paper(openalex_id="W2")]
    api = Api(
        openalex_client=_FakeOpenAlex(search_results=candidates), crossref_client=_FakeCrossref()
    )
    api.resolve("some title")
    res = api.confirm_candidate(1)
    assert res["status"] == "resolved"
    assert api._root.openalex_id == "W2"


def test_api_confirm_candidate_invalid_index():
    api = Api()
    res = api.confirm_candidate(0)
    assert res["status"] == "error"


# -- ficheros (pick_pdf / pick_save_path) --------------------------------------


def test_api_pick_pdf_without_window_returns_none():
    api = Api()
    assert api.pick_pdf() is None


def test_api_pick_pdf_uses_window_dialog():
    window = _FakeWindow(dialog_result=("C:/papers/a.pdf",))
    api = Api()
    api.bind_window(window)
    assert api.pick_pdf() == "C:/papers/a.pdf"
    assert window.calls[0][1]["file_types"] == ("Archivos PDF (*.pdf)",)


def test_api_pick_save_path_uses_window_dialog():
    window = _FakeWindow(dialog_result=("C:/out/bib.bib",))
    api = Api()
    api.bind_window(window)
    assert api.pick_save_path("bib.bib") == "C:/out/bib.bib"


# -- Api.search -----------------------------------------------------------------


def test_api_search_without_root_errors():
    api = Api()
    res = api.search({})
    assert res["status"] == "error"


def test_api_search_uses_resolved_root():
    root = _paper()
    api = Api(
        openalex_client=_FakeOpenAlex(resolve_result=root), crossref_client=_FakeCrossref()
    )
    api.resolve("10.1/abc")

    res = api.search({"generations": "1", "max_articles": "5", "modes": ["references"]})
    assert res["status"] == "ok"
    assert res["count"] == 1
    assert api._results == [root]


def test_api_search_rejects_bad_params():
    api = Api()
    api._root = _paper()
    res = api.search({"generations": "99"})
    assert res["status"] == "error"


# -- Api.export -------------------------------------------------------------------


def test_api_export_without_results_errors(tmp_path):
    api = Api()
    res = api.export(str(tmp_path / "out.bib"), "bibtex")
    assert res["status"] == "error"


def test_api_export_writes_file(tmp_path):
    api = Api()
    api._results = [_paper()]
    path = str(tmp_path / "out.bib")
    res = api.export(path, "bibtex")
    assert res["status"] == "ok"
    assert (tmp_path / "out.bib").exists()


def test_api_export_unknown_format_errors(tmp_path):
    api = Api()
    api._results = [_paper()]
    res = api.export(str(tmp_path / "out.xyz"), "nope")
    assert res["status"] == "error"


def test_api_export_excludes_indices(tmp_path):
    api = Api()
    api._results = [
        _paper(openalex_id="W1", title="Keep me"),
        _paper(openalex_id="W2", title="Discard me"),
        _paper(openalex_id="W3", title="Keep me too"),
    ]
    path = str(tmp_path / "out.bib")
    res = api.export(path, "bibtex", excluded_indices=[1])
    assert res["status"] == "ok"
    assert res["count"] == 2
    content = (tmp_path / "out.bib").read_text(encoding="utf-8")
    assert "Discard me" not in content
    assert "Keep me" in content
    assert "Keep me too" in content


def test_api_export_without_excluded_indices_keeps_everyone(tmp_path):
    api = Api()
    api._results = [_paper(openalex_id="W1"), _paper(openalex_id="W2")]
    res = api.export(str(tmp_path / "out.bib"), "bibtex")
    assert res["count"] == 2


# -- Api.get_settings / save_settings ------------------------------------------


def test_api_get_and_save_settings(tmp_path, monkeypatch):
    monkeypatch.delenv("CONTACT_EMAIL", raising=False)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    api = Api()
    assert api.get_settings() == {"contact_email": "", "semantic_scholar_api_key": ""}

    res = api.save_settings(
        {"CONTACT_EMAIL": "me@example.com", "SEMANTIC_SCHOLAR_API_KEY": "abc123"}
    )
    assert res["status"] == "ok"
    assert api.get_settings() == {
        "contact_email": "me@example.com",
        "semantic_scholar_api_key": "abc123",
    }
    assert (tmp_path / ".env").exists()

    # deja el entorno del proceso tal como estaba antes del test
    monkeypatch.delenv("CONTACT_EMAIL", raising=False)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)


# -- save_env_settings ----------------------------------------------------------


def test_save_env_settings_preserves_unrelated_lines(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("SOME_OTHER_VAR=keep-me\nCONTACT_EMAIL=old@example.com\n", encoding="utf-8")
    save_env_settings({"CONTACT_EMAIL": "new@example.com"}, env_path=env_path)
    content = env_path.read_text(encoding="utf-8")
    assert "SOME_OTHER_VAR=keep-me" in content
    assert "CONTACT_EMAIL=new@example.com" in content
    assert "old@example.com" not in content


def test_save_env_settings_creates_new_file(tmp_path):
    env_path = tmp_path / ".env"
    save_env_settings({"CONTACT_EMAIL": "a@b.com"}, env_path=env_path)
    assert "CONTACT_EMAIL=a@b.com" in env_path.read_text(encoding="utf-8")


# -- _config_from_params ----------------------------------------------------------


def test_config_from_params_defaults():
    config = _config_from_params({})
    assert config.generations == 2
    assert config.allowed_doc_types is None
    assert config.require_open_access is False


def test_config_from_params_doc_type_filter():
    config = _config_from_params({"allowed_doc_types": ["article", "preprint"]})
    assert config.allowed_doc_types == {"article", "preprint"}
