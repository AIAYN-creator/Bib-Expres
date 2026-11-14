from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DiscoveryMode(str, Enum):
    ROOT = "root"
    REFERENCE = "reference"
    CITATION = "citation"
    SIMILAR = "similar"


@dataclass(frozen=True)
class Concept:
    name: str
    score: float


@dataclass
class Paper:
    openalex_id: str
    doi: str | None
    title: str
    authors: list[str]
    year: int | None
    venue: str | None
    concepts: list[Concept]
    citation_count: int
    generation: int
    discovered_via: DiscoveryMode
    relevance_score: float | None = None
    doc_type: str | None = None
    open_access: bool | None = None
    abstract: str | None = None
    topic: str | None = None
    keywords: list[str] = field(default_factory=list)
    language: str | None = None  # ISO 639-1 segun OpenAlex: 'en', 'es'...
    # Editorial y su cadena de matrices segun OpenAlex: ['Cell Press', 'Elsevier BV']
    publisher_lineage: list[str] = field(default_factory=list)
    oa_url: str | None = None  # enlace a la version abierta, si la hay
    oa_status: str | None = None  # gold / green / hybrid / bronze / closed...
    # Calculados por access.annotate_access(), no vienen de la API:
    access_status: str | None = None
    access_url: str | None = None
