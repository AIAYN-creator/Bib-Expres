from __future__ import annotations

import os
from pathlib import Path

import webview
from dotenv import load_dotenv

from ..config import ExpansionMode, InstallConfig, RelevanceWeights, SearchConfig
from ..expansion import expand
from ..export import write
from ..models import Paper
from ..resolve import (
    DOIResolutionError,
    TitleSearchRequired,
    resolve_input,
    search_by_title,
)
from ..sources.crossref import CrossrefClient
from ..sources.openalex import OpenAlexClient
from ..sources.semantic_scholar import SemanticScholarClient

_STATIC_DIR = Path(__file__).parent / "static"
_ENV_KEYS = ("CONTACT_EMAIL", "SEMANTIC_SCHOLAR_API_KEY")


def _paper_to_dict(paper: Paper) -> dict:
    return {
        "title": paper.title,
        "authors": paper.authors,
        "year": paper.year,
        "venue": paper.venue,
        "doi": paper.doi,
        "citation_count": paper.citation_count,
        "relevance_score": paper.relevance_score,
        "doc_type": paper.doc_type,
        "open_access": paper.open_access,
        "abstract": paper.abstract,
    }


def _config_from_params(params: dict) -> SearchConfig:
    raw_modes = params.get("modes") or ["references", "citations"]
    allowed_doc_types = set(params["allowed_doc_types"]) if params.get("allowed_doc_types") else None
    return SearchConfig(
        generations=int(params.get("generations", 2)),
        max_articles=int(params.get("max_articles", 200)),
        max_fanout_per_node=int(params.get("max_fanout", 20)),
        modes={ExpansionMode(m) for m in raw_modes},
        relevance_weights=RelevanceWeights(
            topic=float(params.get("weight_topic", 1.0)),
            citations=float(params.get("weight_citations", 0.2)),
            recency=float(params.get("weight_recency", 0.1)),
        ),
        relevance_threshold=float(params.get("relevance_threshold", 0.3)),
        allowed_doc_types=allowed_doc_types,
        require_open_access=bool(params.get("require_open_access", False)),
    )


def save_env_settings(settings: dict, env_path: Path | None = None) -> None:
    """Lee el .env existente (si lo hay), actualiza solo las claves conocidas y
    reescribe -- no toca ninguna otra linea/clave que ya hubiera."""
    path = env_path or Path(".env")
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    written: set[str] = set()
    new_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped and not stripped.startswith("#") else None
        if key in _ENV_KEYS and key in settings:
            new_lines.append(f"{key}={settings[key]}")
            written.add(key)
        else:
            new_lines.append(line)

    for key in _ENV_KEYS:
        if key in settings and key not in written and settings[key]:
            new_lines.append(f"{key}={settings[key]}")

    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


class Api:
    """Puente js_api de pywebview -- cada metodo publico es llamable desde JS via
    `pywebview.api.<metodo>(...)`. pywebview despacha cada llamada en su propio
    hilo (ver webview/util.py: `Thread(target=_call)`), asi que expand() puede
    tardar sin congelar la ventana -- no hace falta gestionar hilos a mano aqui.
    """

    def __init__(
        self,
        openalex_client: OpenAlexClient | None = None,
        crossref_client: CrossrefClient | None = None,
        semantic_scholar_client: SemanticScholarClient | None = None,
    ) -> None:
        self._openalex = openalex_client or OpenAlexClient()
        self._crossref = crossref_client or CrossrefClient()
        self._semantic_scholar = semantic_scholar_client
        self._window: webview.Window | None = None
        self._root: Paper | None = None
        self._candidates: list[Paper] = []
        self._results: list[Paper] = []

    def bind_window(self, window: webview.Window) -> None:
        self._window = window

    # -- Pantalla 1 / 1b: identificar el paper padre -------------------------

    def resolve(self, raw: str) -> dict:
        try:
            self._root = resolve_input(
                raw, openalex_client=self._openalex, crossref_client=self._crossref
            )
            return {"status": "resolved", "paper": _paper_to_dict(self._root)}
        except TitleSearchRequired as exc:
            self._candidates = search_by_title(exc.query, self._openalex)
            return {
                "status": "needs_confirmation",
                "query": exc.query,
                "candidates": [_paper_to_dict(p) for p in self._candidates],
            }
        except DOIResolutionError as exc:
            return {"status": "error", "message": str(exc)}

    def confirm_candidate(self, index: int) -> dict:
        if not 0 <= index < len(self._candidates):
            return {"status": "error", "message": "seleccion invalida"}
        self._root = self._candidates[index]
        return {"status": "resolved", "paper": _paper_to_dict(self._root)}

    def pick_pdf(self) -> str | None:
        if self._window is None:
            return None
        result = self._window.create_file_dialog(
            webview.FileDialog.OPEN, file_types=("Archivos PDF (*.pdf)",)
        )
        return result[0] if result else None

    # -- Pantalla 2/3/4: parametros, busqueda, resultados ---------------------

    def search(self, params: dict) -> dict:
        if self._root is None:
            return {"status": "error", "message": "no hay paper padre resuelto todavia"}
        try:
            config = _config_from_params(params)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}

        install = InstallConfig.from_env()
        semantic_scholar = self._semantic_scholar or SemanticScholarClient(
            api_key=install.semantic_scholar_api_key, openalex_client=self._openalex
        )
        self._results = expand(
            self._root,
            config,
            openalex_client=self._openalex,
            semantic_scholar_client=semantic_scholar,
        )
        return {
            "status": "ok",
            "count": len(self._results),
            "papers": [_paper_to_dict(p) for p in self._results],
        }

    # -- Pantalla 5: exportar --------------------------------------------------

    def pick_save_path(self, default_name: str = "bibliografia.bib") -> str | None:
        if self._window is None:
            return None
        result = self._window.create_file_dialog(
            webview.FileDialog.SAVE, save_filename=default_name
        )
        return result[0] if result else None

    def export(self, path: str, format: str, excluded_indices: list[int] | None = None) -> dict:
        if not self._results:
            return {"status": "error", "message": "no hay resultados que exportar"}
        excluded = set(excluded_indices or [])
        papers = [p for i, p in enumerate(self._results) if i not in excluded]
        try:
            write(papers, path, format=format)
        except (OSError, ValueError) as exc:
            return {"status": "error", "message": str(exc)}
        return {"status": "ok", "path": path, "count": len(papers)}

    # -- Ajustes ------------------------------------------------------------

    def get_settings(self) -> dict:
        return {
            "contact_email": os.environ.get("CONTACT_EMAIL", ""),
            "semantic_scholar_api_key": os.environ.get("SEMANTIC_SCHOLAR_API_KEY", ""),
        }

    def save_settings(self, settings: dict) -> dict:
        save_env_settings(settings)
        for key in _ENV_KEYS:
            if settings.get(key):
                os.environ[key] = settings[key]
        return {"status": "ok"}


def main() -> None:
    load_dotenv()
    api = Api()
    window = webview.create_window(
        "bib-exprés",
        str(_STATIC_DIR / "index.html"),
        js_api=api,
        width=960,
        height=720,
        min_size=(720, 560),
    )
    api.bind_window(window)
    webview.start()


if __name__ == "__main__":
    main()
