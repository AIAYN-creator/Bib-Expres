"""Banco de pruebas del algoritmo de bib_exprés.

Para cada caso de benchmarks/cases.json:
  1. La "respuesta correcta" es la bibliografia de una revision publicada
     (sus referencias en OpenAlex), sin contar el propio paper de partida.
  2. Se lanza bib_exprés desde el paper de partida con la configuracion por
     defecto (o la que se pase por linea de comandos).
  3. Se ordenan los resultados por score de relevancia -- como los veria alguien
     que ordena el Excel por "Relevancia" -- y se mide:
       - recall@N:    de la bibliografia de la revision, que fraccion aparece
                      entre los N primeros resultados.
       - precision@N: de los N primeros resultados, que fraccion esta en esa
                      bibliografia.

Es una medida aproximada y conservadora: un paper relevante que la revision no
cito cuenta como "fallo". Sirve para comparar versiones del algoritmo entre si
con los mismos casos, no como nota absoluta.

Uso (desde la raiz del repo):
    python benchmarks/run_benchmark.py --label baseline-v2
    python benchmarks/run_benchmark.py --cases benchmarks/cases.json --label prueba --max-articles 300
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import quote

from bib_expres import __version__
from bib_expres.config import SearchConfig
from bib_expres.expansion import expand
from bib_expres.models import Paper
from bib_expres.resolve import resolve_root_paper
from bib_expres.sources.crossref import CrossrefClient
from bib_expres.sources.openalex import OpenAlexClient

CUTOFFS = (50, 100, 200)
RESULTS_DIR = Path(__file__).parent / "results"


@dataclass
class CaseResult:
    case_id: str
    truth_size: int
    returned: int
    seconds: float
    recall: dict[int, float]
    precision: dict[int, float]
    hits_total: int


def rank_by_relevance(papers: list[Paper], exclude_ids: set[str]) -> list[Paper]:
    """Orden en el que el usuario veria los resultados al ordenar por relevancia.
    El orden de llegada de expand() es por exploracion, no por score."""
    kept = [p for p in papers if p.openalex_id not in exclude_ids]
    return sorted(kept, key=lambda p: p.relevance_score or 0.0, reverse=True)


def recall_at(ranked_ids: list[str], truth: set[str], n: int) -> float:
    if not truth:
        return 0.0
    return len(set(ranked_ids[:n]) & truth) / len(truth)


def precision_at(ranked_ids: list[str], truth: set[str], n: int) -> float:
    top = ranked_ids[:n]
    if not top:
        return 0.0
    return len(set(top) & truth) / len(top)


def review_references(openalex: OpenAlexClient, review_doi: str) -> tuple[str, set[str]]:
    raw = openalex._client.get(f"/works/doi:{quote(review_doi, safe='')}")
    review_id = raw["id"].rsplit("/", 1)[-1]
    refs = {u.rsplit("/", 1)[-1] for u in raw.get("referenced_works", [])}
    return review_id, refs


def run_case(case: dict, config: SearchConfig, openalex: OpenAlexClient, crossref: CrossrefClient) -> CaseResult:
    review_id, truth = review_references(openalex, case["review_doi"])
    seed = resolve_root_paper(case["seed_doi"], openalex_client=openalex, crossref_client=crossref)
    truth.discard(seed.openalex_id)

    started = time.monotonic()
    results = expand(seed, config, openalex_client=openalex)
    seconds = time.monotonic() - started

    # Ni el seed ni la propia revision cuentan: la revision cita al seed, asi que
    # suele aparecer entre sus citas, y encontrarla no dice nada del algoritmo.
    ranked = [p.openalex_id for p in rank_by_relevance(results, {seed.openalex_id, review_id})]
    return CaseResult(
        case_id=case["id"],
        truth_size=len(truth),
        returned=len(ranked),
        seconds=seconds,
        recall={n: recall_at(ranked, truth, n) for n in CUTOFFS},
        precision={n: precision_at(ranked, truth, n) for n in CUTOFFS},
        hits_total=len(set(ranked) & truth),
    )


def to_markdown(results: list[CaseResult], label: str, config: SearchConfig) -> str:
    lines = [
        f"## {label} -- {date.today().isoformat()} -- bib_expres {__version__}",
        "",
        f"Configuracion: generaciones={config.generations}, max_articles={config.max_articles}, "
        f"fanout={config.max_fanout_per_node}, modos={sorted(m.value for m in config.modes)}, "
        f"umbral={config.relevance_threshold}, pesos={config.relevance_weights}",
        "",
        "| Caso | Bibliografia revision | Devueltos | Aciertos | "
        + " | ".join(f"Recall@{n}" for n in CUTOFFS)
        + " | "
        + " | ".join(f"Prec@{n}" for n in CUTOFFS)
        + " | Tiempo |",
        "|---|---|---|---|" + "---|" * (2 * len(CUTOFFS)) + "---|",
    ]
    for r in results:
        lines.append(
            f"| {r.case_id} | {r.truth_size} | {r.returned} | {r.hits_total} | "
            + " | ".join(f"{r.recall[n]:.1%}" for n in CUTOFFS)
            + " | "
            + " | ".join(f"{r.precision[n]:.1%}" for n in CUTOFFS)
            + f" | {r.seconds:.0f} s |"
        )
    mean = {n: sum(r.recall[n] for r in results) / len(results) for n in CUTOFFS}
    lines.append(
        "| **media** | | | | " + " | ".join(f"**{mean[n]:.1%}**" for n in CUTOFFS) + " |" + " |" * len(CUTOFFS) + " |"
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cases", default=str(Path(__file__).parent / "cases.json"))
    parser.add_argument("--label", default="sin-etiqueta")
    parser.add_argument("--max-articles", type=int, default=200)
    parser.add_argument("--generations", type=int, default=2)
    parser.add_argument("--only", help="Ejecutar solo este caso (id)")
    args = parser.parse_args(argv)

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))["cases"]
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]
    config = SearchConfig(max_articles=args.max_articles, generations=args.generations)
    openalex, crossref = OpenAlexClient(), CrossrefClient()

    results = []
    for case in cases:
        print(f"[{case['id']}] {case['seed_label']} -> {case['review_label']}", file=sys.stderr)
        results.append(run_case(case, config, openalex, crossref))

    report = to_markdown(results, args.label, config)
    print(report)
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{date.today().isoformat()}-{args.label}.md"
    out.write_text(report, encoding="utf-8")
    print(f"Guardado en {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
