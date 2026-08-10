from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


class ExpansionMode(str, Enum):
    REFERENCES = "references"
    CITATIONS = "citations"
    SIMILAR = "similar"


@dataclass
class RelevanceWeights:
    topic: float = 1.0
    citations: float = 0.2
    recency: float = 0.1


@dataclass
class SearchConfig:
    generations: int = 2
    max_articles: int = 200
    max_fanout_per_node: int = 20
    modes: set[ExpansionMode] = field(
        default_factory=lambda: {ExpansionMode.REFERENCES, ExpansionMode.CITATIONS}
    )
    relevance_weights: RelevanceWeights = field(default_factory=RelevanceWeights)
    relevance_threshold: float = 0.3
    allowed_doc_types: set[str] | None = None  # None = sin filtro, cualquier tipo entra
    require_open_access: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.generations <= 5:
            raise ValueError("generations debe estar entre 1 y 5")


@dataclass
class InstallConfig:
    contact_email: str | None
    semantic_scholar_api_key: str | None

    @classmethod
    def from_env(cls) -> "InstallConfig":
        return cls(
            contact_email=os.environ.get("CONTACT_EMAIL") or None,
            semantic_scholar_api_key=os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or None,
        )
