from __future__ import annotations

import os
import threading
import time
import webbrowser
from pathlib import Path

import webview
from dotenv import load_dotenv

from ..access import (
    ACCESS_LABELS,
    TEST_DOI,
    AccessConfig,
    annotate_access,
    format_publishers,
    is_openable_url,
    library_link,
    publisher_counts,
    validate_library_template,
)
from ..config import ExpansionMode, InstallConfig, RelevanceWeights, SearchConfig
from ..expansion import ProgressEvent, expand, planned_expansions
from ..relevance import explain
from ..export import write
from ..models import Paper
from ..resolve import (
    DOIResolutionError,
    TitleSearchRequired,
    resolve_input,
    search_by_title,
)
from ..sources.base import RateLimitedError
from ..sources.crossref import CrossrefClient
from ..sources.openalex import OpenAlexClient
from ..sources.semantic_scholar import SemanticScholarClient

_STATIC_DIR = Path(__file__).parent / "static"
_ENV_KEYS = (
    "CONTACT_EMAIL",
    "SEMANTIC_SCHOLAR_API_KEY",
    "LIBRARY_LINK_TEMPLATE",
    "SUBSCRIBED_PUBLISHERS",
)


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
        "language": paper.language,
        "publisher": paper.publisher_lineage[-1] if paper.publisher_lineage else None,
        "access_status": paper.access_status,
        "access_label": ACCESS_LABELS.get(paper.access_status or "", None),
        "access_url": paper.access_url if is_openable_url(paper.access_url) else None,
        "explanation": explain(paper.score_breakdown),
    }


def _config_from_params(params: dict) -> SearchConfig:
    raw_modes = params.get("modes") or ["references", "citations"]
    allowed_doc_types = set(params["allowed_doc_types"]) if params.get("allowed_doc_types") else None
    language_mode = params.get("language_mode", "any")
    if language_mode not in ("any", "same", "custom"):
        raise ValueError(f"modo de idioma desconocido: {language_mode}")
    languages = None
    if language_mode == "custom":
        languages = {c.strip().lower() for c in str(params.get("languages", "")).split(",") if c.strip()}
        if not languages:
            raise ValueError("elige al menos un idioma (codigos como es, en)")
    return SearchConfig(
        generations=int(params.get("generations", 2)),
        max_articles=int(params.get("max_articles", 200)),
        max_fanout_per_node=int(params.get("max_fanout", 20)),
        modes={ExpansionMode(m) for m in raw_modes},
        relevance_weights=RelevanceWeights(
            topic=float(params.get("weight_topic", 1.0)),
            citations=float(params.get("weight_citations", 0.2)),
            recency=float(params.get("weight_recency", 0.1)),
            coupling=float(params.get("weight_coupling", 1.0)),
            keywords=float(params.get("weight_keywords", 0.5)),
        ),
        explore_budget=int(params.get("explore_budget", 30)),
        relevance_threshold=float(params.get("relevance_threshold", 0.15)),
        allowed_doc_types=allowed_doc_types,
        require_open_access=bool(params.get("require_open_access", False)),
        languages=languages,
        same_language_as_root=language_mode == "same",
    )


def _clean_env_value(value: object) -> str:
    """Quita espacios/saltos de linea de los extremos (una API key pegada con un
    salto de linea al final es lo normal) y rechaza saltos de linea internos, que
    meterian lineas extra en el .env."""
    cleaned = str(value).strip()
    if "\n" in cleaned or "\r" in cleaned:
        raise ValueError("los ajustes no pueden contener saltos de linea")
    return cleaned


def save_env_settings(settings: dict, env_path: Path | None = None) -> None:
    """Lee el .env existente (si lo hay), actualiza solo las claves conocidas y
    reescribe -- no toca ninguna otra linea/clave que ya hubiera."""
    settings = {k: _clean_env_value(v) for k, v in settings.items() if k in _ENV_KEYS}
    if "LIBRARY_LINK_TEMPLATE" in settings:
        settings["LIBRARY_LINK_TEMPLATE"] = validate_library_template(settings["LIBRARY_LINK_TEMPLATE"])
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
        # Estado de la busqueda en curso. search() corre en un hilo de pywebview y
        # get_progress()/cancel_search() en otros, de ahi el lock.
        self._progress_lock = threading.Lock()
        self._progress: ProgressEvent | None = None
        self._last_activity: float | None = None
        self._cancel_requested = threading.Event()

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
        except (DOIResolutionError, RateLimitedError) as exc:
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
        self._cancel_requested.clear()
        with self._progress_lock:
            self._progress = ProgressEvent(
                explored=0, planned=planned_expansions(config), candidates=0,
                generation=0, current_title=None,
            )
            self._last_activity = time.monotonic()
        try:
            self._results = expand(
                self._root,
                config,
                openalex_client=self._openalex,
                semantic_scholar_client=semantic_scholar,
                on_progress=self._record_progress,
                should_cancel=self._cancel_requested.is_set,
            )
        except RateLimitedError as exc:
            self._record_progress(
                ProgressEvent(
                    explored=0, planned=planned_expansions(config), candidates=0,
                    generation=0, current_title=None, finished=True,
                )
            )
            return {"status": "error", "message": str(exc)}
        access = self._access_config()
        annotate_access(self._results, access)
        return {
            "status": "ok",
            "count": len(self._results),
            "cancelled": self._cancel_requested.is_set(),
            "papers": [_paper_to_dict(p) for p in self._results],
            "publishers": publisher_counts(self._results[1:]),
            "selected_publishers": sorted(access.publishers),
        }

    def _record_progress(self, event: ProgressEvent) -> None:
        with self._progress_lock:
            self._progress = event
            self._last_activity = time.monotonic()

    # -- Acceso institucional ---------------------------------------------------

    @staticmethod
    def _access_config() -> AccessConfig:
        install = InstallConfig.from_env()
        try:
            return AccessConfig.from_strings(
                install.library_link_template, install.subscribed_publishers
            )
        except ValueError:
            # Plantilla invalida en un .env editado a mano: se ignora la plantilla
            # en vez de tumbar la busqueda; Ajustes la marcara al guardar.
            return AccessConfig.from_strings(None, install.subscribed_publishers)

    def set_publishers(self, publishers: list[str]) -> dict:
        """Guarda las editoriales marcadas y recalcula el acceso de los resultados
        ya obtenidos, sin repetir la busqueda."""
        chosen = {str(p).strip() for p in publishers or [] if str(p).strip()}
        try:
            save_env_settings({"SUBSCRIBED_PUBLISHERS": format_publishers(chosen)})
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        os.environ["SUBSCRIBED_PUBLISHERS"] = format_publishers(chosen)
        annotate_access(self._results, self._access_config())
        return {"status": "ok", "papers": [_paper_to_dict(p) for p in self._results]}

    def open_link(self, url: str) -> dict:
        """Abre un enlace en el navegador del sistema (no dentro de la app). Solo
        http(s): las URLs de acceso abierto vienen de una API externa."""
        if not is_openable_url(url):
            return {"status": "error", "message": "enlace no valido"}
        webbrowser.open(url)
        return {"status": "ok"}

    def test_library_link(self, template: str) -> dict:
        try:
            cleaned = validate_library_template(template)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        if not cleaned:
            return {"status": "error", "message": "escribe primero la plantilla"}
        url = library_link(cleaned, TEST_DOI)
        webbrowser.open(url)
        return {"status": "ok", "url": url}

    def get_progress(self) -> dict:
        """Lo consulta la GUI cada ~0,5 s mientras dura search(). `idle_seconds`
        (tiempo desde la ultima actividad) es lo que responde a "¿se ha caido?"."""
        with self._progress_lock:
            event = self._progress
            last = self._last_activity
        if event is None:
            return {"status": "idle"}
        return {
            "status": "finished" if event.finished else "running",
            "explored": event.explored,
            "planned": event.planned,
            "candidates": event.candidates,
            "generation": event.generation,
            "current_title": event.current_title,
            "cancelled": event.cancelled,
            "idle_seconds": round(time.monotonic() - last, 1) if last is not None else 0.0,
        }

    def cancel_search(self) -> dict:
        """Pide parar; search() termina en cuanto acabe el paper que esta
        procesando y devuelve lo encontrado hasta ese momento."""
        self._cancel_requested.set()
        return {"status": "ok"}

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
            "library_link_template": os.environ.get("LIBRARY_LINK_TEMPLATE", ""),
        }

    def save_settings(self, settings: dict) -> dict:
        try:
            save_env_settings(settings)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        for key in _ENV_KEYS:
            if key in settings:
                os.environ[key] = _clean_env_value(settings[key])
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
