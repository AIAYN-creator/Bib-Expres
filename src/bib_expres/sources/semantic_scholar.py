from __future__ import annotations

import dataclasses
from urllib.parse import quote

from ..models import DiscoveryMode, Paper
from .base import SourceClient
from .openalex import OpenAlexClient

SEMANTIC_SCHOLAR_BASE_URL = "https://api.semanticscholar.org"


class SemanticScholarClient:
    """Complemento: unico con endpoint de "articulos similares". Descubre DOIs
    candidatos via recomendaciones y los resuelve a Paper via OpenAlex, para que
    toda la metadata salga de una unica fuente canonica y el resultado se pueda
    seguir expandiendo igual que cualquier otro paper. Requiere API key gratuita
    para buen rate limit."""

    def __init__(
        self,
        api_key: str | None = None,
        openalex_client: OpenAlexClient | None = None,
        **kwargs,
    ) -> None:
        self._client = SourceClient(
            base_url=SEMANTIC_SCHOLAR_BASE_URL,
            api_key=api_key,
            api_key_header="x-api-key",
            **kwargs,
        )
        self._openalex = openalex_client or OpenAlexClient(**kwargs)

    def get_similar(self, paper: Paper, generation: int, limit: int = 20) -> list[Paper]:
        if not paper.doi:
            return []

        raw = self._client.get(
            f"/recommendations/v1/papers/forpaper/DOI:{quote(paper.doi, safe='')}",
            params={"fields": "externalIds", "limit": limit},
        )

        results: list[Paper] = []
        for candidate in raw.get("recommendedPapers", []):
            candidate_doi = (candidate.get("externalIds") or {}).get("DOI")
            if not candidate_doi:
                continue
            resolved = self._openalex.resolve_doi(candidate_doi)
            if resolved is not None:
                results.append(
                    dataclasses.replace(
                        resolved, generation=generation, discovered_via=DiscoveryMode.SIMILAR
                    )
                )
        return results
