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
    """Relevancia tematica (la formula de v1/v2): media ponderada de solapamiento
    tematico, citas normalizadas (log) y recencia, en [0, 1]. En v3 es una de las
    tres senales del score final -- ver final_score()."""
    return thematic_components(paper, parent, weights, current_year)["relevancia"]


def thematic_components(
    paper: Paper,
    parent: Paper,
    weights: RelevanceWeights,
    current_year: int | None = None,
) -> dict[str, float]:
    if current_year is None:
        current_year = date.today().year

    topic = _topic_overlap(paper, parent)
    citations = _citations_normalized(paper)
    recency = _recency_normalized(paper, current_year)

    total_weight = weights.topic + weights.citations + weights.recency
    raw = weights.topic * topic + weights.citations * citations + weights.recency * recency
    return {
        "tema": topic,
        "citas": citations,
        "recencia": recency,
        "relevancia": raw / total_weight if total_weight else 0.0,
    }


COUPLING_SATURATION = 5  # a partir de 5 conexiones la senal ya no crece


def coupling_score(connections: int) -> float:
    """Conexiones = en cuantos papers explorados aparece este (como referencia o
    cita). Una sola aparicion es lo minimo para estar en el pool, asi que cuenta 0;
    crece en escala log y satura en COUPLING_SATURATION."""
    extra = max(connections - 1, 0)
    return min(1.0, math.log1p(extra) / math.log1p(COUPLING_SATURATION))


def shared_keywords(paper: Paper, parent: Paper) -> list[str]:
    parent_kw = {k.lower(): k for k in parent.keywords}
    return sorted({parent_kw[k.lower()] for k in paper.keywords if k.lower() in parent_kw})


def keyword_score(paper: Paper, parent: Paper) -> float:
    """Jaccard entre palabras clave de OpenAlex (sin distinguir mayusculas)."""
    a = {k.lower() for k in paper.keywords}
    b = {k.lower() for k in parent.keywords}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def final_score(
    paper: Paper,
    parent: Paper,
    weights: RelevanceWeights,
    connections: int,
    current_year: int | None = None,
) -> tuple[float, dict]:
    """Score final de v3, en [0, 1], y su desglose:
    (relevancia tematica + w_conexiones * conexiones + w_palabras * palabras clave)
    / (1 + w_conexiones + w_palabras)."""
    thematic = thematic_components(paper, parent, weights, current_year)
    coupling = coupling_score(connections)
    keywords = keyword_score(paper, parent)
    denominator = 1 + weights.coupling + weights.keywords
    total = (
        thematic["relevancia"] + weights.coupling * coupling + weights.keywords * keywords
    ) / denominator
    breakdown = {
        **thematic,
        "conexiones": connections,
        "conexiones_score": coupling,
        "palabras_clave": shared_keywords(paper, parent),
        "palabras_clave_score": keywords,
        "final": total,
    }
    return total, breakdown


def explain(breakdown: dict | None) -> str:
    """Una linea legible: por que este articulo esta donde esta."""
    if not breakdown:
        return ""
    parts = [
        f"relevancia {breakdown['relevancia']:.2f} (tema {breakdown['tema']:.2f}, "
        f"citas {breakdown['citas']:.2f}, recencia {breakdown['recencia']:.2f})"
    ]
    n = breakdown.get("conexiones", 0)
    if n > 1:
        parts.append(f"conectado con {n} papers de la búsqueda")
    else:
        parts.append("conectado con 1 paper de la búsqueda")
    kws = breakdown.get("palabras_clave") or []
    if kws:
        shown = ", ".join(kws[:4]) + ("..." if len(kws) > 4 else "")
        parts.append(f"comparte: {shown}")
    return f"{breakdown['final']:.2f} = " + " · ".join(parts)


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
