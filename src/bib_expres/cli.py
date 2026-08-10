from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from .config import ExpansionMode, InstallConfig, RelevanceWeights, SearchConfig
from .expansion import expand
from .export import infer_format, write
from .models import Paper
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bib-expres",
        description="Snowballing bibliografico a partir de un paper padre (DOI).",
    )
    parser.add_argument("--version", action="version", version="0.1.0")
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
        default=0.3,
        help="Umbral minimo de relevancia, 0-1",
    )
    parser.add_argument(
        "--weight-topic", type=float, default=1.0, help="Peso del solapamiento tematico"
    )
    parser.add_argument("--weight-citations", type=float, default=0.2, help="Peso de las citas")
    parser.add_argument("--weight-recency", type=float, default=0.1, help="Peso de la recencia")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Fichero de salida")
    parser.add_argument(
        "--format",
        choices=["bibtex", "ris", "csljson"],
        default=None,
        help="Formato de salida; por defecto se infiere de la extension de --output",
    )
    return parser


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
            ),
            relevance_threshold=args.relevance_threshold,
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
        root, config, openalex_client=openalex, semantic_scholar_client=semantic_scholar
    )

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
