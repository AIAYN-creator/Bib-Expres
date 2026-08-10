from __future__ import annotations

from dataclasses import dataclass
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
