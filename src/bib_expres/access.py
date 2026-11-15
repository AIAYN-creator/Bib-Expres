"""Acceso a los papers: version abierta, enlace via biblioteca y un filtro
aproximado "solo lo que puedo leer" (ver investigacion-acceso-institucional-v3).

No existe ninguna fuente publica que diga si tu institucion tiene acceso a un
paper concreto, asi que aqui se combina lo que si se sabe:
  - si es de acceso abierto (OpenAlex), y el enlace a esa version;
  - si su editorial (o una editorial matriz) esta en la lista que el usuario
    marca como cubierta por su institucion -- aproximado: un contrato no siempre
    cubre todas las revistas ni todos los anos;
  - un enlace a traves del proxy/resolvedor de la biblioteca, para que el login
    lo haga el navegador. bib_exprés nunca pasa peticiones por ese proxy ni
    guarda credenciales: solo construye enlaces.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import quote, urlsplit

from .models import Paper

OPEN = "open"
OPEN_BRONZE = "open_bronze"
INSTITUTION = "institution"
UNKNOWN = "unknown"
NONE = "none"

ACCESS_LABELS = {
    OPEN: "abierto",
    OPEN_BRONZE: "abierto (bronze)",
    INSTITUTION: "institución (editorial marcada)",
    UNKNOWN: "no comprobado",
    NONE: "sin acceso conocido",
}

ACCESS_LABELS_EN = {
    OPEN: "open",
    OPEN_BRONZE: "open (bronze)",
    INSTITUTION: "institution (ticked publisher)",
    UNKNOWN: "unchecked",
    NONE: "no known access",
}


def access_label(status: str | None, lang: str = "es") -> str | None:
    labels = ACCESS_LABELS_EN if lang == "en" else ACCESS_LABELS
    return labels.get(status or "", None)


MAX_TEMPLATE_LENGTH = 500
TEST_DOI = "10.1038/nature14539"  # paper conocido para el boton "Probar"


class InvalidLibraryTemplate(ValueError):
    pass


def validate_library_template(template: str) -> str:
    """Solo https, con host, sin espacios ni saltos de linea. Devuelve la
    plantilla limpia o lanza InvalidLibraryTemplate con un mensaje para el usuario."""
    cleaned = (template or "").strip()
    if not cleaned:
        return ""
    if len(cleaned) > MAX_TEMPLATE_LENGTH:
        raise InvalidLibraryTemplate("la plantilla es demasiado larga")
    if any(ch.isspace() for ch in cleaned):
        raise InvalidLibraryTemplate("la plantilla no puede contener espacios ni saltos de linea")
    parts = urlsplit(cleaned.replace("{doi}", "x").replace("{url}", "x"))
    if parts.scheme != "https":
        raise InvalidLibraryTemplate("la plantilla debe empezar por https://")
    if not parts.netloc:
        raise InvalidLibraryTemplate("la plantilla no tiene dominio")
    return cleaned


def library_link(template: str, doi: str | None) -> str | None:
    """Enlace al paper a traves de la biblioteca. Con {doi} o {url} en la
    plantilla se sustituyen; sin ellos, la plantilla es un prefijo (p.ej. el
    `login?url=` de EZproxy) al que se le anade la URL de doi.org. Los valores
    se escapan: un DOI raro no puede alterar el enlace."""
    if not template or not doi:
        return None
    doi_url = "https://doi.org/" + quote(doi, safe="/")
    if "{doi}" in template or "{url}" in template:
        return template.replace("{doi}", quote(doi, safe="/")).replace("{url}", quote(doi_url, safe=""))
    return template + quote(doi_url, safe="")


def is_openable_url(url: str | None) -> bool:
    """Lo unico que la GUI abre en el navegador: http(s) con dominio. Nada de
    file:, javascript: ni similares (oa_url viene de una API externa)."""
    if not url:
        return False
    parts = urlsplit(url)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


@dataclass
class AccessConfig:
    library_template: str = ""
    publishers: set[str] = field(default_factory=set)

    @classmethod
    def from_strings(cls, template: str | None, publishers: str | None) -> "AccessConfig":
        return cls(
            library_template=validate_library_template(template or ""),
            publishers=parse_publishers(publishers),
        )


def parse_publishers(raw: str | None) -> set[str]:
    """Lista guardada como texto, separada por ';' (los nombres de editorial
    llevan comas: 'Springer Science+Business Media, LLC')."""
    if not raw:
        return set()
    return {p.strip() for p in raw.split(";") if p.strip()}


def format_publishers(publishers: set[str]) -> str:
    return "; ".join(sorted(publishers))


def access_status(paper: Paper, publishers: set[str]) -> str:
    if paper.open_access:
        return OPEN_BRONZE if paper.oa_status == "bronze" else OPEN
    if publishers and paper.publisher_lineage:
        if any(name in publishers for name in paper.publisher_lineage):
            return INSTITUTION
        return NONE
    # Sin lista de editoriales, o sin editorial conocida: no hay con que
    # comprobarlo -- un dato que falta no se trata como "sin acceso".
    return UNKNOWN


def annotate_access(papers: list[Paper], config: AccessConfig) -> None:
    """Rellena access_status y access_url de cada paper. access_url: la version
    abierta si existe; si no, el enlace via biblioteca (si hay plantilla)."""
    for paper in papers:
        paper.access_status = access_status(paper, config.publishers)
        if paper.open_access and is_openable_url(paper.oa_url):
            paper.access_url = paper.oa_url
        else:
            paper.access_url = library_link(config.library_template, paper.doi)


def is_readable(status: str | None, include_unknown: bool = True) -> bool:
    if status in (OPEN, OPEN_BRONZE, INSTITUTION):
        return True
    if status == UNKNOWN or status is None:
        return include_unknown
    return False


def publisher_counts(papers: list[Paper]) -> list[tuple[str, int]]:
    """Editoriales presentes en los resultados, agrupadas por la editorial matriz
    (ultima de la cadena: Cell Press -> Elsevier BV), de mas a menos frecuente.
    Es lo que la GUI ofrece para marcar."""
    counts: Counter[str] = Counter()
    for paper in papers:
        if paper.publisher_lineage:
            counts[paper.publisher_lineage[-1]] += 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
