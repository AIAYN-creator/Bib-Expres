from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass
from typing import Callable

import requests

from .config import ExpansionMode, SearchConfig
from .models import Paper
from .relevance import dedup_key, meets_threshold, score
from .sources.openalex import OpenAlexClient
from .sources.semantic_scholar import SemanticScholarClient


@dataclass(frozen=True)
class ProgressEvent:
    """Foto del estado de la busqueda, para pintar una barra de progreso.

    `found / max_articles` es el progreso real hacia el tope. Si el grafo se
    agota antes de llegar al tope, la busqueda acaba con `found < max_articles`
    y `finished=True` -- quien pinte la barra debe saltar al 100% y explicarlo,
    no quedarse a medias."""

    found: int
    max_articles: int
    generation: int
    current_title: str | None
    finished: bool = False
    cancelled: bool = False


ProgressCallback = Callable[[ProgressEvent], None]


def expand(
    root: Paper,
    config: SearchConfig,
    openalex_client: OpenAlexClient | None = None,
    semantic_scholar_client: SemanticScholarClient | None = None,
    on_progress: ProgressCallback | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> list[Paper]:
    """Bucle best-first: explora primero los candidatos con mayor score de
    relevancia, respetando limite de generaciones, tope total y fanout por nodo.
    No lee configuracion de instalacion (API keys, contact email) -- eso lo hace
    quien construya los clientes antes de llamar aqui (implementacion-cli).

    `on_progress` se llama antes y despues de pedir los candidatos de cada paper
    (la parte lenta, de red) y una vez al final. `should_cancel` se comprueba en
    cada vuelta: si devuelve True, se para y se devuelve lo encontrado hasta ahi."""
    openalex = openalex_client or OpenAlexClient()
    similar_client = semantic_scholar_client
    if ExpansionMode.SIMILAR in config.modes and similar_client is None:
        similar_client = SemanticScholarClient(openalex_client=openalex)

    allowed_languages = _effective_languages(root, config)
    root.relevance_score = 1.0  # el padre siempre es el punto de partida, no se puntua contra si mismo
    seen: dict[str, Paper] = {dedup_key(root): root}
    results: list[Paper] = [root]

    counter = itertools.count()  # desempate estable para el heap (Paper no es comparable)
    frontier: list[tuple[float, int, Paper]] = []
    heapq.heappush(frontier, (-1.0, next(counter), root))

    def report(current: Paper | None, finished: bool = False, cancelled: bool = False) -> None:
        if on_progress is None:
            return
        on_progress(
            ProgressEvent(
                found=len(results),
                max_articles=config.max_articles,
                generation=current.generation + 1 if current is not None else 0,
                current_title=current.title if current is not None else None,
                finished=finished,
                cancelled=cancelled,
            )
        )

    cancelled = False
    while frontier and len(results) < config.max_articles:
        if should_cancel is not None and should_cancel():
            cancelled = True
            break

        _neg_score, _, current = heapq.heappop(frontier)

        if current.generation >= config.generations:
            continue

        report(current)
        candidates = _fetch_candidates(current, config, openalex, similar_client)

        scored_candidates = []
        for candidate in candidates:
            key = dedup_key(candidate)
            if key in seen:
                continue
            candidate.relevance_score = score(candidate, root, config.relevance_weights)
            if not meets_threshold(candidate, config.relevance_threshold):
                continue
            if config.allowed_doc_types and candidate.doc_type not in config.allowed_doc_types:
                continue
            if config.require_open_access and not candidate.open_access:
                continue
            if (
                allowed_languages is not None
                and candidate.language is not None
                and candidate.language not in allowed_languages
            ):
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
        report(current)

    report(None, finished=True, cancelled=cancelled)
    return results


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
