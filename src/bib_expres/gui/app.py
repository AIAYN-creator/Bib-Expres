from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import webview
from dotenv import load_dotenv
from webview.dom import DOMEventHandler

from ..access import (
    ACCESS_LABELS,
    access_label,
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
from . import notify as sysnotify
from ..models import Paper
from ..resolve import (
    DOIResolutionError,
    TitleSearchRequired,
    resolve_input,
    search_by_title,
)
from ..sources.base import RateLimitedError, quota_status
from ..sources.crossref import CrossrefClient
from ..sources.openalex import OpenAlexClient
from ..sources.semantic_scholar import SemanticScholarClient

_STATIC_DIR = Path(__file__).parent / "static"
_ENV_KEYS = (
    "CONTACT_EMAIL",
    "SEMANTIC_SCHOLAR_API_KEY",
    "LIBRARY_LINK_TEMPLATE",
    "SUBSCRIBED_PUBLISHERS",
    "UI_LANGUAGE",
    "UI_THEME",
    "UI_NOTIFY",
)
_UI_LANGUAGES = ("es", "en")
# Peticiones a OpenAlex de una busqueda por defecto, medidas en validacion-e2e-v3
# (74 con la cache vacia). Sirve para traducir la cuota a "busquedas que quedan".
REQUESTS_PER_SEARCH = 75
_OPENALEX_HOST = "api.openalex.org"


def quota_summary() -> dict:
    q = quota_status(_OPENALEX_HOST)
    if not q or q.get("remaining") is None:
        return {"known": False}
    limit = q.get("limit")
    return {
        "known": True,
        "remaining": q["remaining"],
        "limit": limit,
        "reset_in": q.get("reset_in"),
        "searches_left": q["remaining"] // REQUESTS_PER_SEARCH,
        "searches_total": (limit // REQUESTS_PER_SEARCH) if limit else None,
    }
_UI_THEMES = ("system", "light", "dark")
_UI_NOTIFY = ("on", "off")

# Textos del aviso del sistema (la GUI pasa su idioma).
_NOTIFY_TEXT = {
    "es": {
        "done": "Búsqueda terminada",
        "done_body": "{count} artículos de {candidates} candidatos · {title}",
        "cancelled": "Búsqueda cancelada",
        "failed": "La búsqueda se ha detenido",
        "test": "Así te avisará bib_exprés",
        "test_body": "Cuando una búsqueda termine y estés en otra ventana.",
    },
    "en": {
        "done": "Search finished",
        "done_body": "{count} articles out of {candidates} candidates · {title}",
        "cancelled": "Search cancelled",
        "failed": "The search stopped",
        "test": "This is how bib_exprés will let you know",
        "test_body": "When a search finishes while you're in another window.",
    },
}


def _error(code: str, message: str = "", **data) -> dict:
    """Error para la GUI: `code` es lo que el frontend traduce (es/en); `message`
    es el detalle en espanol, que se muestra tal cual en la interfaz en espanol."""
    return {"status": "error", "code": code, "message": message, **data}


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
        "access_label_en": access_label(paper.access_status, "en"),
        "access_url": paper.access_url if is_openable_url(paper.access_url) else None,
        "explanation": explain(paper.score_breakdown),
        # El frontend pinta el desglose en el idioma de la interfaz a partir de esto
        "score_breakdown": paper.score_breakdown,
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


def _quote_env_value(value: str) -> str:
    """Entre comillas dobles: sin ellas, python-dotenv corta el valor en un " #"
    (lo toma por comentario) -- p.ej. una editorial "Wiley #2 Press"."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def save_env_settings(settings: dict, env_path: Path | None = None) -> None:
    """Lee el .env existente (si lo hay), actualiza solo las claves conocidas y
    reescribe -- no toca ninguna otra linea/clave que ya hubiera."""
    settings = {k: _clean_env_value(v) for k, v in settings.items() if k in _ENV_KEYS}
    if settings.get("UI_LANGUAGE") and settings["UI_LANGUAGE"] not in _UI_LANGUAGES:
        raise ValueError("idioma de la interfaz no valido")
    if settings.get("UI_THEME") and settings["UI_THEME"] not in _UI_THEMES:
        raise ValueError("tema no valido")
    if settings.get("UI_NOTIFY") and settings["UI_NOTIFY"] not in _UI_NOTIFY:
        raise ValueError("valor de aviso no valido")
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
            new_lines.append(f"{key}={_quote_env_value(settings[key])}")
            written.add(key)
        else:
            new_lines.append(line)

    for key in _ENV_KEYS:
        if key in settings and key not in written and settings[key]:
            new_lines.append(f"{key}={_quote_env_value(settings[key])}")

    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


class Api:
    """Puente js_api de pywebview -- cada metodo publico (sin _ delante) es
    llamable desde JS via `pywebview.api.<metodo>(...)`: lo interno va con _. pywebview despacha cada llamada en su propio
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
        self._last_export_path: Path | None = None
        # Rutas elegidas por el usuario en el dialogo nativo de guardar: export()
        # solo escribe en una de ellas, nunca en una ruta que llegue solo de JS.
        self._chosen_save_paths: set[Path] = set()

    def _bind_window(self, window: webview.Window) -> None:
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
            return _error("resolve_failed", str(exc))
        except RateLimitedError as exc:
            return _rate_limited(exc)

    def confirm_candidate(self, index: int) -> dict:
        if not 0 <= index < len(self._candidates):
            return _error("invalid_selection", "selección inválida")
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
            return _error("no_root", "no hay paper padre resuelto todavía")
        try:
            config = _config_from_params(params)
        except ValueError as exc:
            return _error("invalid_params", str(exc))

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
            return _rate_limited(exc)
        access = self._access_config()
        annotate_access(self._results, access)
        with self._progress_lock:
            candidates = self._progress.candidates if self._progress else len(self._results)
        return {
            "status": "ok",
            "count": len(self._results),
            "candidates": candidates,
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
            return _error("invalid_settings", str(exc))
        os.environ["SUBSCRIBED_PUBLISHERS"] = format_publishers(chosen)
        annotate_access(self._results, self._access_config())
        return {"status": "ok", "papers": [_paper_to_dict(p) for p in self._results]}

    def open_link(self, url: str) -> dict:
        """Abre un enlace en el navegador del sistema (no dentro de la app). Solo
        http(s): las URLs de acceso abierto vienen de una API externa."""
        if not is_openable_url(url):
            return _error("invalid_link", "enlace no válido")
        webbrowser.open(url)
        return {"status": "ok"}

    def test_library_link(self, template: str) -> dict:
        try:
            cleaned = validate_library_template(template)
        except ValueError as exc:
            return _error("invalid_library_link", str(exc))
        if not cleaned:
            return _error("empty_library_link", "escribe primero el enlace")
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

    def get_quota(self) -> dict:
        """Cuota diaria de OpenAlex segun sus propias cabeceras: la GUI la ensena
        como "busquedas que quedan hoy" y cuando se reinicia."""
        return quota_summary()

    # -- Aviso al terminar --------------------------------------------------------

    def notify_search_done(self, info: dict) -> dict:
        """La GUI lo llama al terminar una busqueda si la ventana no tiene el foco.
        Los numeros y el titulo se recalculan aqui a partir de lo que de verdad se
        busco: de la pagina solo se toman el idioma y el desenlace."""
        if os.environ.get("UI_NOTIFY", "on") == "off":
            return {"status": "ok", "shown": False}
        info = info or {}
        text = _NOTIFY_TEXT["en" if info.get("lang") == "en" else "es"]
        outcome = info.get("outcome")
        if outcome == "error":
            title, body = text["failed"], str(info.get("message") or "")
        else:
            with self._progress_lock:
                candidates = self._progress.candidates if self._progress else len(self._results)
            title = text["cancelled"] if outcome == "cancelled" else text["done"]
            body = text["done_body"].format(
                count=len(self._results), candidates=candidates,
                title=self._root.title if self._root else "",
            )
        return {"status": "ok", "shown": sysnotify.notify(title, body)}

    def test_notification(self, lang: str = "es") -> dict:
        text = _NOTIFY_TEXT["en" if lang == "en" else "es"]
        return {"status": "ok", "shown": sysnotify.notify(text["test"], text["test_body"])}

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
        if not result:
            return None
        chosen = result if isinstance(result, str) else result[0]
        self._chosen_save_paths.add(Path(chosen).resolve())
        return chosen

    def export(
        self,
        path: str,
        format: str,
        excluded_indices: list[int] | None = None,
        lang: str = "es",
    ) -> dict:
        if not self._results:
            return _error("nothing_to_export", "no hay resultados que exportar")
        if Path(path).resolve() not in self._chosen_save_paths:
            return _error("path_not_chosen", "elige dónde guardar con el botón «Elegir…»")
        excluded = set(excluded_indices or [])
        papers = [p for i, p in enumerate(self._results) if i not in excluded]
        try:
            write(papers, path, format=format, lang=lang if lang in _UI_LANGUAGES else "es")
        except (OSError, ValueError) as exc:
            return _error("export_failed", str(exc))
        self._last_export_path = Path(path)
        return {"status": "ok", "path": path, "name": Path(path).name, "count": len(papers)}

    def open_export_folder(self) -> dict:
        """Abre en el explorador la carpeta del ultimo fichero exportado en esta
        sesion -- nunca una ruta que llegue de JS."""
        if self._last_export_path is None or not self._last_export_path.parent.is_dir():
            return _error("no_export_folder", "no hay ninguna exportación todavía")
        folder = str(self._last_export_path.parent)
        if sys.platform == "win32":
            os.startfile(folder)  # noqa: S606 -- carpeta propia, no una orden
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder])
        return {"status": "ok"}

    # -- Ajustes ------------------------------------------------------------

    def get_settings(self) -> dict:
        return {
            "contact_email": os.environ.get("CONTACT_EMAIL", ""),
            "semantic_scholar_api_key": os.environ.get("SEMANTIC_SCHOLAR_API_KEY", ""),
            "library_link_template": os.environ.get("LIBRARY_LINK_TEMPLATE", ""),
            "ui_language": os.environ.get("UI_LANGUAGE", ""),
            "ui_theme": os.environ.get("UI_THEME", "") or "system",
            "ui_notify": os.environ.get("UI_NOTIFY", "") or "on",
        }

    def save_settings(self, settings: dict) -> dict:
        try:
            save_env_settings(settings)
        except ValueError as exc:
            return _error("invalid_settings", str(exc))
        for key in _ENV_KEYS:
            if key in settings:
                os.environ[key] = _clean_env_value(settings[key])
        return {"status": "ok"}


def _rate_limited(exc: RateLimitedError) -> dict:
    return _error("rate_limited", str(exc), source=exc.source, wait_seconds=exc.retry_after)


def _bind_pdf_drop(window: webview.Window) -> None:
    """Soltar un PDF en la ventana: el navegador no da la ruta real del fichero a
    JS, pero pywebview si a Python (`pywebviewFullPath`). Se la pasamos a la GUI,
    que la trata igual que si se hubiera elegido con el boton."""

    def on_drop(event: dict) -> None:
        files = (event.get("dataTransfer") or {}).get("files") or []
        for file in files:
            path = file.get("pywebviewFullPath")
            if path and str(path).lower().endswith(".pdf"):
                window.evaluate_js(f"window.bibExpres && window.bibExpres.onPdfDropped({json.dumps(path)})")
                return

    window.dom.document.events.dragover += DOMEventHandler(lambda e: None, True, True, debounce=500)
    window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)


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
    api._bind_window(window)
    webview.start(_bind_pdf_drop, window)


if __name__ == "__main__":
    main()
