from __future__ import annotations

import math
import re
from datetime import date

from .config import RelevanceWeights
from .models import Paper

MAX_CITATIONS_REFERENCE = 10_000
RECENCY_WINDOW_YEARS = 30


def _topic_overlap(paper: Paper, parent: Paper) -> float:
    if not paper.concepts or not parent.concepts:
        return 0.0
    parent_scores = {c.name: c.score for c in parent.concepts}
    overlap = sum(
        c.score * parent_scores[c.name] for c in paper.concepts if c.name in parent_scores
    )
    norm = math.sqrt(
        sum(c.score**2 for c in paper.concepts) * sum(s**2 for s in parent_scores.values())
    )
    return overlap / norm if norm else 0.0


def _citations_normalized(paper: Paper) -> float:
    value = math.log1p(paper.citation_count) / math.log1p(MAX_CITATIONS_REFERENCE)
    return min(1.0, value)


def _recency_normalized(paper: Paper, current_year: int) -> float:
    if paper.year is None:
        return 0.0
    age = max(current_year - paper.year, 0)
    return max(0.0, 1.0 - age / RECENCY_WINDOW_YEARS)


def score(
    paper: Paper,
    parent: Paper,
    weights: RelevanceWeights,
    current_year: int | None = None,
) -> float:
    """Formula simple y transparente: media ponderada de solapamiento tematico,
    citas normalizadas (log) y recencia. Se mantiene en [0, 1], tal como asume
    SearchConfig.relevance_threshold."""
    if current_year is None:
        current_year = date.today().year

    topic = _topic_overlap(paper, parent)
    citations = _citations_normalized(paper)
    recency = _recency_normalized(paper, current_year)

    total_weight = weights.topic + weights.citations + weights.recency
    if total_weight == 0:
        return 0.0

    raw = weights.topic * topic + weights.citations * citations + weights.recency * recency
    return raw / total_weight


def meets_threshold(paper: Paper, threshold: float) -> bool:
    return (paper.relevance_score or 0.0) >= threshold


def _normalize_title(title: str) -> str:
    normalized = title.lower()
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def dedup_key(paper: Paper) -> str:
    """DOI primero (clave sin ambiguedad); si no hay DOI, titulo normalizado +
    primer autor + año como fallback."""
    if paper.doi:
        return f"doi:{paper.doi.lower()}"
    first_author = paper.authors[0].lower() if paper.authors else ""
    return f"title:{_normalize_title(paper.title)}:{first_author}:{paper.year or ''}"


def deduplicate(papers: list[Paper]) -> list[Paper]:
    seen: dict[str, Paper] = {}
    for paper in papers:
        key = dedup_key(paper)
        existing = seen.get(key)
        if existing is None or (paper.relevance_score or 0) > (existing.relevance_score or 0):
            seen[key] = paper
    return list(seen.values())
