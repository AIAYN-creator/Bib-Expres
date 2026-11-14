from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from . import __version__
from .access import AccessConfig, InvalidLibraryTemplate, annotate_access, is_readable
from .config import ExpansionMode, InstallConfig, RelevanceWeights, SearchConfig
from .expansion import ProgressEvent, expand
from .export import infer_format, write
from .models import Paper
from .relevance import explain
from .resolve import (
    DOIResolutionError,
    TitleSearchRequired,
    resolve_input,
    resolve_root_paper,
    search_by_title,
)
from .sources.crossref import CrossrefClient
from .sources.openalex import OpenAlexClient
from .sources.semantic_scholar import SemanticScholarClient

DEFAULT_OUTPUT = "bibliografia.bib"


def _parse_modes(raw: str) -> set[ExpansionMode]:
    modes: set[ExpansionMode] = set()
    for name in raw.split(","):
        name = name.strip()
        if not name:
            continue
        try:
            modes.add(ExpansionMode(name))
        except ValueError:
            valid = ", ".join(m.value for m in ExpansionMode)
            raise argparse.ArgumentTypeError(f"modo desconocido '{name}' -- validos: {valid}")
    if not modes:
        raise argparse.ArgumentTypeError("--modes no puede quedar vacio")
    return modes


def _parse_doc_types(raw: str) -> set[str]:
    return {t.strip() for t in raw.split(",") if t.strip()}


def _parse_language(raw: str) -> str | set[str] | None:
    """'any' -> None (sin filtro), 'same' -> idioma del paper padre,
    'es,en' -> esos codigos."""
    value = raw.strip().lower()
    if value in ("", "any"):
        return None
    if value == "same":
        return "same"
    codes = {c.strip() for c in value.split(",") if c.strip()}
    if not all(c.isalpha() and 2 <= len(c) <= 3 for c in codes):
        raise argparse.ArgumentTypeError(
            f"idioma no valido: '{raw}' -- usa any, same, o codigos ISO como es,en"
        )
    return codes


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bib-expres",
        description="Snowballing bibliografico a partir de un paper padre (DOI).",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--doi", help="DOI del paper padre (atajo directo, sin autodeteccion)")
    parser.add_argument(
        "--input",
        help="DOI, ID/URL de arXiv, ruta a un PDF, o titulo del paper padre "
        "(autodetecta el tipo; usa --doi si ya sabes que es un DOI)",
    )
    parser.add_argument("--generations", type=int, default=2, help="Generaciones a expandir (1-5)")
    parser.add_argument("--max-articles", type=int, default=200, help="Tope total de articulos")
    parser.add_argument(
        "--max-fanout", type=int, default=20, help="Tope de candidatos nuevos por paper"
    )
    parser.add_argument(
        "--modes",
        type=_parse_modes,
        default={ExpansionMode.REFERENCES, ExpansionMode.CITATIONS},
        help="Modos de expansion activos, separados por coma: references,citations,similar",
    )
    parser.add_argument(
        "--relevance-threshold",
        type=float,
        default=0.15,
        help="Umbral minimo de relevancia, 0-1",
    )
    parser.add_argument(
        "--weight-topic", type=float, default=1.0, help="Peso del solapamiento tematico"
    )
    parser.add_argument("--weight-citations", type=float, default=0.2, help="Peso de las citas")
    parser.add_argument("--weight-recency", type=float, default=0.1, help="Peso de la recencia")
    parser.add_argument(
        "--doc-types",
        type=_parse_doc_types,
        default=None,
        help="Tipos de documento permitidos, separados por coma (p.ej. article,preprint); "
        "por defecto, todos",
    )
    parser.add_argument(
        "--open-access-only", action="store_true", help="Solo incluir articulos de acceso abierto"
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Fichero de salida")
    parser.add_argument(
        "--format",
        choices=["bibtex", "ris", "csljson", "xlsx"],
        default=None,
        help="Formato de salida; por defecto se infiere de la extension de --output",
    )
    parser.add_argument(
        "--language",
        type=_parse_language,
        default=None,
        help="Idioma de los articulos: any (cualquiera, por defecto), same (el del "
        "paper padre) o codigos ISO separados por coma (p.ej. es,en). Los articulos "
        "sin idioma conocido no se descartan.",
    )
    parser.add_argument(
        "--weight-coupling",
        type=float,
        default=1.0,
        help="Peso de las conexiones (en cuantos papers de la busqueda aparece) en el score final",
    )
    parser.add_argument(
        "--weight-keywords",
        type=float,
        default=0.5,
        help="Peso de las palabras clave en comun con el paper padre en el score final",
    )
    parser.add_argument(
        "--explore-budget",
        type=int,
        default=30,
        help="Maximo de papers a expandir (pedir sus referencias/citas); acota el tiempo",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Mostrar en stderr el desglose del score de los 20 primeros resultados",
    )
    parser.add_argument(
        "--library-link",
        default=None,
        help="Plantilla de enlace de tu biblioteca (EZproxy, OpenAthens, OpenURL), p.ej. "
        "https://proxy.tu-uni.es/login?url= -- admite {doi} y {url}. Por defecto, "
        "LIBRARY_LINK_TEMPLATE del .env",
    )
    parser.add_argument(
        "--publishers",
        default=None,
        help="Editoriales que cubre tu institucion, separadas por ';' (p.ej. "
        "'Elsevier BV;Springer Nature'). Por defecto, SUBSCRIBED_PUBLISHERS del .env",
    )
    parser.add_argument(
        "--accessible-only",
        action="store_true",
        help="Quitar del resultado lo que no puedes leer: ni abierto ni de una editorial "
        "marcada. Los articulos sin datos para comprobarlo se mantienen",
    )
    parser.add_argument(
        "--strict-access",
        action="store_true",
        help="Con --accessible-only, quitar tambien los articulos cuyo acceso no se puede comprobar",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="No mostrar la linea de progreso durante la busqueda",
    )
    return parser


_PROGRESS_WIDTH = 100


def _print_progress(event: ProgressEvent) -> None:
    """Una sola linea en stderr que se reescribe con \r (sin codigos ANSI, que
    no todas las consolas de Windows entienden) -- stdout queda para el resultado."""
    if event.finished:
        line = ""
    else:
        title = (event.current_title or "")[:45]
        line = (
            f"explorados {event.explored}/{event.planned} -- {event.candidates} candidatos"
            f" -- generacion {event.generation} -- {title}"
        )
    sys.stderr.write("\r" + line[:_PROGRESS_WIDTH].ljust(_PROGRESS_WIDTH) + ("\r" if not line else ""))
    sys.stderr.flush()


def _confirm_title_candidate(query: str, openalex_client: OpenAlexClient) -> Paper | None:
    """Prompt interactivo simple: lista numerada de candidatos, elegir numero o
    cancelar. Nunca se auto-selecciona el primero -- la busqueda por titulo es
    ambigua por naturaleza (ver input-formatos-v2)."""
    candidates = search_by_title(query, openalex_client)
    if not candidates:
        print(f"No se encontraron resultados para '{query}'.", file=sys.stderr)
        return None

    print(f"Varios resultados para '{query}':", file=sys.stderr)
    for i, paper in enumerate(candidates, start=1):
        authors = ", ".join(paper.authors[:3]) or "autores desconocidos"
        print(f"  {i}. {paper.title} ({paper.year or 's.f.'}) -- {authors}", file=sys.stderr)

    choice = input("Elige un numero (Enter para cancelar): ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(candidates)):
        return None
    return candidates[int(choice) - 1]


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.doi and not args.input:
        parser.error("hace falta --doi o --input")

    try:
        config = SearchConfig(
            generations=args.generations,
            max_articles=args.max_articles,
            max_fanout_per_node=args.max_fanout,
            modes=args.modes,
            relevance_weights=RelevanceWeights(
                topic=args.weight_topic,
                citations=args.weight_citations,
                recency=args.weight_recency,
                coupling=args.weight_coupling,
                keywords=args.weight_keywords,
            ),
            explore_budget=args.explore_budget,
            relevance_threshold=args.relevance_threshold,
            allowed_doc_types=args.doc_types,
            require_open_access=args.open_access_only,
            languages=args.language if isinstance(args.language, set) else None,
            same_language_as_root=args.language == "same",
        )
    except ValueError as exc:
        print(f"Error de configuracion: {exc}", file=sys.stderr)
        return 1

    install = InstallConfig.from_env()
    if ExpansionMode.SIMILAR in config.modes and not install.semantic_scholar_api_key:
        print(
            "Aviso: modo 'similar' activo sin SEMANTIC_SCHOLAR_API_KEY configurada "
            "-- funcionara con un rate limit mucho mas bajo.",
            file=sys.stderr,
        )

    try:
        access_config = AccessConfig.from_strings(
            args.library_link if args.library_link is not None else install.library_link_template,
            args.publishers if args.publishers is not None else install.subscribed_publishers,
        )
    except InvalidLibraryTemplate as exc:
        print(f"Error en la plantilla de enlace de la biblioteca: {exc}", file=sys.stderr)
        return 1

    openalex = OpenAlexClient(contact_email=install.contact_email)
    crossref = CrossrefClient(contact_email=install.contact_email)
    semantic_scholar = SemanticScholarClient(
        api_key=install.semantic_scholar_api_key, openalex_client=openalex
    )

    try:
        if args.doi:
            root = resolve_root_paper(args.doi, openalex_client=openalex, crossref_client=crossref)
        else:
            root = resolve_input(args.input, openalex_client=openalex, crossref_client=crossref)
    except DOIResolutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except TitleSearchRequired as exc:
        confirmed = _confirm_title_candidate(exc.query, openalex)
        if confirmed is None:
            print("Cancelado.", file=sys.stderr)
            return 1
        root = confirmed

    results = expand(
        root,
        config,
        openalex_client=openalex,
        semantic_scholar_client=semantic_scholar,
        on_progress=None if args.quiet else _print_progress,
    )

    if args.explain:
        for paper in results[1:21]:
            print(f"- {paper.title[:70]}\n    {explain(paper.score_breakdown)}", file=sys.stderr)

    annotate_access(results, access_config)
    if args.accessible_only:
        before = len(results)
        results = [
            p
            for p in results
            if p is root or is_readable(p.access_status, include_unknown=not args.strict_access)
        ]
        print(f"{before - len(results)} articulos quitados por --accessible-only", file=sys.stderr)

    output_format = args.format or infer_format(args.output)
    try:
        write(results, args.output, format=output_format)
    except OSError as exc:
        print(f"Error al escribir '{args.output}': {exc}", file=sys.stderr)
        return 1

    print(f"{len(results)} articulos escritos en {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
