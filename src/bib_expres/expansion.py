from __future__ import annotations

import heapq
import itertools

import requests

from .config import ExpansionMode, SearchConfig
from .models import Paper
from .relevance import dedup_key, meets_threshold, score
from .sources.openalex import OpenAlexClient
from .sources.semantic_scholar import SemanticScholarClient


def expand(
    root: Paper,
    config: SearchConfig,
    openalex_client: OpenAlexClient | None = None,
    semantic_scholar_client: SemanticScholarClient | None = None,
) -> list[Paper]:
    """Bucle best-first: explora primero los candidatos con mayor score de
    relevancia, respetando limite de generaciones, tope total y fanout por nodo.
    No lee configuracion de instalacion (API keys, contact email) -- eso lo hace
    quien construya los clientes antes de llamar aqui (implementacion-cli)."""
    openalex = openalex_client or OpenAlexClient()
    similar_client = semantic_scholar_client
    if ExpansionMode.SIMILAR in config.modes and similar_client is None:
        similar_client = SemanticScholarClient(openalex_client=openalex)

    root.relevance_score = 1.0  # el padre siempre es el punto de partida, no se puntua contra si mismo
    seen: dict[str, Paper] = {dedup_key(root): root}
    results: list[Paper] = [root]

    counter = itertools.count()  # desempate estable para el heap (Paper no es comparable)
    frontier: list[tuple[float, int, Paper]] = []
    heapq.heappush(frontier, (-1.0, next(counter), root))

    while frontier and len(results) < config.max_articles:
        _neg_score, _, current = heapq.heappop(frontier)

        if current.generation >= config.generations:
            continue

        candidates = _fetch_candidates(current, config, openalex, similar_client)

        scored_candidates = []
        for candidate in candidates:
            key = dedup_key(candidate)
            if key in seen:
                continue
            candidate.relevance_score = score(candidate, root, config.relevance_weights)
            if not meets_threshold(candidate, config.relevance_threshold):
                continue
            seen[key] = candidate
            scored_candidates.append(candidate)

        scored_candidates.sort(key=lambda p: p.relevance_score or 0.0, reverse=True)
        for candidate in scored_candidates[: config.max_fanout_per_node]:
            if len(results) >= config.max_articles:
                break
            results.append(candidate)
            heapq.heappush(
                frontier, (-(candidate.relevance_score or 0.0), next(counter), candidate)
            )

    return results


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
