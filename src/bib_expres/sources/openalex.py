from __future__ import annotations

import requests

from ..models import Concept, DiscoveryMode, Paper
from .base import SourceClient

OPENALEX_BASE_URL = "https://api.openalex.org"
BATCH_SIZE = 50


def _strip_openalex_id(value: str) -> str:
    return value.rsplit("/", 1)[-1]


def _strip_doi(value: str | None) -> str | None:
    if not value:
        return None
    return value.rsplit("doi.org/", 1)[-1]


def _parse_work(
    raw: dict,
    *,
    generation: int = 0,
    discovered_via: DiscoveryMode = DiscoveryMode.ROOT,
) -> Paper:
    authors = [
        a["author"]["display_name"]
        for a in raw.get("authorships", [])
        if a.get("author", {}).get("display_name")
    ]
    concepts = [
        Concept(name=c["display_name"], score=c.get("score", 0.0))
        for c in raw.get("concepts", [])
    ]
    primary_location = raw.get("primary_location") or {}
    source = primary_location.get("source") or {}

    return Paper(
        openalex_id=_strip_openalex_id(raw["id"]),
        doi=_strip_doi(raw.get("doi")),
        title=raw.get("display_name") or "(sin titulo)",
        authors=authors,
        year=raw.get("publication_year"),
        venue=source.get("display_name"),
        concepts=concepts,
        citation_count=raw.get("cited_by_count", 0),
        generation=generation,
        discovered_via=discovered_via,
    )


class OpenAlexClient:
    """Fuente primaria: referencias, citas y conceptos/temas. Sin API key."""

    def __init__(self, contact_email: str | None = None, **kwargs) -> None:
        self._client = SourceClient(base_url=OPENALEX_BASE_URL, contact_email=contact_email, **kwargs)

    def resolve_doi(self, doi: str) -> Paper | None:
        try:
            raw = self._client.get(f"/works/doi:{doi}")
        except requests.RequestException:
            return None
        return _parse_work(raw)

    def get_references(self, paper: Paper, generation: int) -> list[Paper]:
        raw = self._client.get(f"/works/{paper.openalex_id}")
        referenced_ids = [_strip_openalex_id(u) for u in raw.get("referenced_works", [])]
        return self._fetch_by_ids(referenced_ids, generation, DiscoveryMode.REFERENCE)

    def get_citations(self, paper: Paper, generation: int, limit: int = 50) -> list[Paper]:
        raw = self._client.get(
            "/works",
            params={"filter": f"cites:{paper.openalex_id}", "per_page": min(limit, 200)},
        )
        return [
            _parse_work(w, generation=generation, discovered_via=DiscoveryMode.CITATION)
            for w in raw.get("results", [])
        ]

    def _fetch_by_ids(
        self, ids: list[str], generation: int, discovered_via: DiscoveryMode
    ) -> list[Paper]:
        papers: list[Paper] = []
        for i in range(0, len(ids), BATCH_SIZE):
            batch = ids[i : i + BATCH_SIZE]
            if not batch:
                continue
            raw = self._client.get(
                "/works",
                params={"filter": f"openalex_id:{'|'.join(batch)}", "per_page": BATCH_SIZE},
            )
            papers.extend(
                _parse_work(w, generation=generation, discovered_via=discovered_via)
                for w in raw.get("results", [])
            )
        return papers
