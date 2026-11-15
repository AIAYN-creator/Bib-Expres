from __future__ import annotations

import heapq
import itertools
from collections import Counter
from dataclasses import dataclass
from typing import Callable

import requests

from .config import ExpansionMode, SearchConfig
from .models import Paper
from .relevance import dedup_key, final_score, meets_threshold, score
from .sources.openalex import OpenAlexClient
from .sources.semantic_scholar import SemanticScholarClient


@dataclass(frozen=True)
class ProgressEvent:
    """Foto del estado de la busqueda, para pintar una barra de progreso.

    v3 explora primero y elige al final, asi que el progreso real es
    `explored / planned`: papers ya expandidos sobre los que se piensa expandir
    (limitado por generaciones, fanout y explore_budget). Si el grafo se agota
    antes, la busqueda acaba con `finished=True` -- quien pinte la barra debe
    saltar al 100%. `candidates` es cuantos articulos distintos se han visto."""

    explored: int
    planned: int
    candidates: int
    generation: int
    current_title: str | None
    finished: bool = False
    cancelled: bool = False


ProgressCallback = Callable[[ProgressEvent], None]


def planned_expansions(config: SearchConfig) -> int:
    """Maximo de papers que se expandiran: 1 + F + F^2 ... hasta la ultima
    generacion que todavia se expande, recortado por explore_budget."""
    total, level = 0, 1
    for _ in range(config.generations):
        total += level
        level *= config.max_fanout_per_node
        if total >= config.explore_budget:
            break
    return min(total, config.explore_budget)


def expand(
    root: Paper,
    config: SearchConfig,
    openalex_client: OpenAlexClient | None = None,
    semantic_scholar_client: SemanticScholarClient | None = None,
    on_progress: ProgressCallback | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> list[Paper]:
    """Algoritmo v3 (ver diseno-algoritmo-v3): explorar ancho, elegir al final.

    1. Exploracion best-first por relevancia tematica, como en v2: de cada paper
       expandido, los `max_fanout_per_node` candidatos nuevos mas relevantes pasan
       a la cola. Se expanden como mucho `explore_budget` papers.
    2. TODO candidato visto se guarda (el "pool"), y se cuenta en cuantos papers
       explorados ha aparecido (sus conexiones).
    3. Al terminar, cada candidato recibe su score final -- relevancia tematica +
       conexiones + palabras clave en comun, con su desglose en
       `paper.score_breakdown` -- y se devuelven los mejores hasta
       `max_articles`, aplicando ahi los filtros y el umbral.

    Los filtros (tipo, acceso abierto, idioma) se aplican al elegir, no al
    explorar: un paper que no quieres en el resultado puede seguir llevando a
    otros que si. El paper padre va siempre el primero.

    `on_progress` se llama antes y despues de expandir cada paper y al final.
    `should_cancel` se comprueba en cada vuelta: si devuelve True, se para de
    explorar y se elige entre lo visto hasta ese momento."""
    openalex = openalex_client or OpenAlexClient()
    similar_client = semantic_scholar_client
    if ExpansionMode.SIMILAR in config.modes and similar_client is None:
        similar_client = SemanticScholarClient(openalex_client=openalex)

    weights = config.relevance_weights
    root.relevance_score = 1.0  # el padre siempre es el punto de partida, no se puntua contra si mismo
    root_key = dedup_key(root)
    pool: dict[str, Paper] = {root_key: root}
    connections: Counter[str] = Counter()
    planned = planned_expansions(config)
    explored = 0

    counter = itertools.count()  # desempate estable para el heap (Paper no es comparable)
    frontier: list[tuple[float, int, Paper]] = []
    heapq.heappush(frontier, (-1.0, next(counter), root))

    def report(current: Paper | None, finished: bool = False, cancelled: bool = False) -> None:
        if on_progress is None:
            return
        on_progress(
            ProgressEvent(
                explored=explored,
                planned=planned,
                candidates=len(pool) - 1,
                generation=current.generation + 1 if current is not None else 0,
                current_title=current.title if current is not None else None,
                finished=finished,
                cancelled=cancelled,
            )
        )

    cancelled = False
    while frontier and explored < config.explore_budget:
        if should_cancel is not None and should_cancel():
            cancelled = True
            break

        _neg_score, _, current = heapq.heappop(frontier)
        if current.generation >= config.generations:
            continue

        report(current)
        candidates = _fetch_candidates(current, config, openalex, similar_client)
        explored += 1

        fresh = []
        for candidate in candidates:
            key = dedup_key(candidate)
            if key == root_key:
                continue
            connections[key] += 1
            if key in pool:
                continue
            candidate.relevance_score = score(candidate, root, weights)
            pool[key] = candidate
            fresh.append(candidate)

        fresh.sort(key=lambda p: p.relevance_score or 0.0, reverse=True)
        for candidate in fresh[: config.max_fanout_per_node]:
            heapq.heappush(
                frontier, (-(candidate.relevance_score or 0.0), next(counter), candidate)
            )
        report(current)

    selected = _select(root, pool, connections, config)
    report(None, finished=True, cancelled=cancelled)
    return selected


def _select(
    root: Paper, pool: dict[str, Paper], connections: Counter, config: SearchConfig
) -> list[Paper]:
    allowed_languages = _effective_languages(root, config)
    chosen: list[Paper] = []
    for key, paper in pool.items():
        if paper is root:
            continue
        total, breakdown = final_score(
            paper, root, config.relevance_weights, connections.get(key, 1)
        )
        paper.relevance_score = total
        paper.score_breakdown = breakdown
        if not meets_threshold(paper, config.relevance_threshold):
            continue
        if config.allowed_doc_types and paper.doc_type not in config.allowed_doc_types:
            continue
        if config.require_open_access and not paper.open_access:
            continue
        if (
            allowed_languages is not None
            and paper.language is not None
            and paper.language not in allowed_languages
        ):
            continue
        chosen.append(paper)
    chosen.sort(key=lambda p: p.relevance_score or 0.0, reverse=True)
    return [root] + chosen[: max(config.max_articles - 1, 0)]


def _effective_languages(root: Paper, config: SearchConfig) -> set[str] | None:
    """None = sin filtro de idioma. "Idioma de la busqueda" = el del paper padre;
    si OpenAlex no lo sabe, no se filtra (mejor de mas que descartar a ciegas)."""
    if config.same_language_as_root:
        return {root.language} if root.language else None
    return config.languages


def _fetch_candidates(
    paper: Paper,
    config: SearchConfig,
    openalex: OpenAlexClient,
    similar_client: SemanticScholarClient | None,
) -> list[Paper]:
    next_generation = paper.generation + 1
    candidates: list[Paper] = []

    if ExpansionMode.REFERENCES in config.modes:
        candidates.extend(
            _safe_fetch(lambda: openalex.get_references(paper, generation=next_generation))
        )
    if ExpansionMode.CITATIONS in config.modes:
        candidates.extend(
            _safe_fetch(lambda: openalex.get_citations(paper, generation=next_generation))
        )
    if ExpansionMode.SIMILAR in config.modes and similar_client is not None:
        candidates.extend(
            _safe_fetch(
                lambda: similar_client.get_similar(
                    paper, generation=next_generation, limit=config.max_fanout_per_node
                )
            )
        )

    return candidates


def _safe_fetch(fetch) -> list[Paper]:
    """Un fallo de red en un nodo no debe tumbar toda la busqueda -- se trata
    como si ese nodo no tuviera candidatos y se sigue con el resto del frontier."""
    try:
        return fetch()
    except requests.RequestException:
        return []
