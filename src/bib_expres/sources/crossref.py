from __future__ import annotations

import requests

from ..models import DiscoveryMode, Paper
from .base import SourceClient

CROSSREF_BASE_URL = "https://api.crossref.org"


def _parse_work(raw: dict) -> Paper:
    authors = [
        f"{a.get('given', '')} {a.get('family', '')}".strip()
        for a in raw.get("author", [])
        if a.get("family")
    ]
    titles = raw.get("title") or []
    venues = raw.get("container-title") or []

    year = None
    for date_field in ("published", "published-print", "published-online"):
        parts = (raw.get(date_field) or {}).get("date-parts")
        if parts and parts[0]:
            year = parts[0][0]
            break

    return Paper(
        openalex_id="",
        doi=raw.get("DOI"),
        title=titles[0] if titles else "(sin titulo)",
        authors=authors,
        year=year,
        venue=venues[0] if venues else None,
        concepts=[],
        citation_count=raw.get("is-referenced-by-count", 0),
        generation=0,
        discovered_via=DiscoveryMode.ROOT,
    )


class CrossrefClient:
    """Autoridad de facto para DOIs: confirma que existen y trae metadata base.
    No devuelve openalex_id -- resolve.py combina esto con OpenAlex para el ID
    canonico que de verdad se usa para expandir el grafo."""

    def __init__(self, contact_email: str | None = None, **kwargs) -> None:
        self._client = SourceClient(base_url=CROSSREF_BASE_URL, contact_email=contact_email, **kwargs)

    def resolve_doi(self, doi: str) -> Paper | None:
        try:
            raw = self._client.get(f"/works/{doi}")
        except requests.RequestException:
            return None
        return _parse_work(raw.get("message", raw))
