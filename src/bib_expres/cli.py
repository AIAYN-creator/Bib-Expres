from __future__ import annotations

import argparse
import sys

from .config import ExpansionMode, InstallConfig, RelevanceWeights, SearchConfig
from .expansion import expand
from .export import write_bibtex
from .resolve import DOIResolutionError, resolve_root_paper
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
    parser.add_argument("--doi", required=True, help="DOI del paper padre")
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
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Fichero de salida BibTeX")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

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
        root = resolve_root_paper(args.doi, openalex_client=openalex, crossref_client=crossref)
    except DOIResolutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    results = expand(
        root, config, openalex_client=openalex, semantic_scholar_client=semantic_scholar
    )

    try:
        write_bibtex(results, args.output)
    except OSError as exc:
        print(f"Error al escribir '{args.output}': {exc}", file=sys.stderr)
        return 1

    print(f"{len(results)} articulos escritos en {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
