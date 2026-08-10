from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .models import Paper
from .sources.crossref import CrossrefClient
from .sources.openalex import OpenAlexClient


class DOIResolutionError(Exception):
    """El DOI no se pudo resolver a un paper utilizable."""


def resolve_root_paper(
    doi: str,
    openalex_client: OpenAlexClient | None = None,
    crossref_client: CrossrefClient | None = None,
) -> Paper:
    """DOI de entrada -> Paper raiz (generacion 0), tal como decide resolucion-input.

    OpenAlex es la fuente que de verdad importa (trae el openalex_id necesario para
    expandir el grafo mas adelante); CrossRef solo entra para confirmar que el DOI
    existe de verdad cuando OpenAlex todavia no lo tiene indexado.
    """
    openalex = openalex_client or OpenAlexClient()
    crossref = crossref_client or CrossrefClient()

    doi = doi.strip()

    paper = openalex.resolve_doi(doi)
    if paper is not None:
        return paper

    crossref_paper = crossref.resolve_doi(doi)
    if crossref_paper is not None:
        raise DOIResolutionError(
            f"El DOI '{doi}' existe (confirmado en CrossRef) pero todavia no esta "
            "indexado en OpenAlex, que es la fuente que se usa para expandir el "
            "grafo de citas. Prueba mas adelante o con otro paper padre."
        )

    raise DOIResolutionError(
        f"No se ha encontrado ningun paper con el DOI '{doi}' ni en OpenAlex ni en "
        "CrossRef. Comprueba que el DOI sea correcto."
    )


_DOI_PATTERN = re.compile(r"10\.\d+/[-._;()/:A-Za-z0-9]+")
_ARXIV_ID_PATTERN = re.compile(r"^(\d{4}\.\d{4,5}|[a-z][a-z-]*/\d{7})(v\d+)?$")


def _looks_like_doi(raw: str) -> str | None:
    candidate = re.sub(r"^https?://(dx\.)?doi\.org/", "", raw.strip(), flags=re.IGNORECASE)
    return candidate if _DOI_PATTERN.fullmatch(candidate) else None


def normalize_arxiv_to_doi(raw: str) -> str | None:
    """ID suelto o URL (arxiv.org/abs/..., arxiv.org/pdf/....pdf) -> DOI de arXiv.

    Desde 2022 arXiv asigna DOI propio a todo articulo, con efecto retroactivo,
    formato fijo 10.48550/arXiv.<id> -- no hace falta ninguna llamada nueva a
    OpenAlex, resolve_root_paper se encarga del resto a partir de aqui.
    """
    candidate = raw.strip()
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^\s?]+)", candidate, re.IGNORECASE)
    if match:
        candidate = match.group(1)
    candidate = candidate.removesuffix(".pdf")

    match = _ARXIV_ID_PATTERN.match(candidate)
    if not match:
        return None
    return f"10.48550/arXiv.{match.group(1)}"


def _find_doi_in_text(text: str) -> str | None:
    match = _DOI_PATTERN.search(text)
    return match.group(0).rstrip(".,;") if match else None


def _guess_title_line(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return max(lines, key=len) if lines else None


def extract_from_pdf(path: str) -> tuple[str | None, str | None]:
    """Texto de las 1-2 primeras paginas (donde casi siempre esta el DOI en PDFs
    de editoriales). Si aparece un DOI, (doi, None) -- camino de mayor confianza.
    Si no, (None, titulo_adivinado) como red de seguridad, nunca se auto-confirma
    (ver TitleSearchRequired). PDFs escaneados sin capa de texto -> (None, None),
    anadir OCR queda fuera de alcance.
    """
    try:
        reader = PdfReader(path)
        text = "".join(page.extract_text() or "" for page in reader.pages[:2])
    except (PdfReadError, OSError):
        return None, None

    doi = _find_doi_in_text(text)
    if doi:
        return doi, None
    return None, _guess_title_line(text)


class TitleSearchRequired(Exception):
    """La entrada no se pudo resolver directamente -- hace falta confirmacion
    humana antes de elegir un candidato como paper padre (ver search_by_title)."""

    def __init__(self, query: str) -> None:
        super().__init__(f"'{query}' no se pudo resolver directo, hace falta buscar por titulo")
        self.query = query


def search_by_title(title: str, openalex_client: OpenAlexClient, limit: int = 5) -> list[Paper]:
    """Devuelve candidatos, nunca resuelve sola -- la busqueda por titulo es
    ambigua por naturaleza, exige confirmacion humana siempre."""
    return openalex_client.search_by_title(title, limit=limit)


def resolve_input(
    raw: str,
    openalex_client: OpenAlexClient | None = None,
    crossref_client: CrossrefClient | None = None,
) -> Paper:
    """DOI, arXiv o PDF con DOI reconocible: resuelve directo, mismo contrato que
    resolve_root_paper (Paper o DOIResolutionError). Texto libre o PDF sin DOI
    reconocible: no resuelve aqui, levanta TitleSearchRequired -- quien llame debe
    usar search_by_title() y pedir confirmacion humana antes de continuar.
    """
    candidate = raw.strip()

    if candidate.lower().endswith(".pdf") and Path(candidate).is_file():
        pdf_doi, pdf_title_guess = extract_from_pdf(candidate)
        if pdf_doi is None:
            raise TitleSearchRequired(pdf_title_guess or Path(candidate).stem)
        candidate = pdf_doi

    doi = _looks_like_doi(candidate) or normalize_arxiv_to_doi(candidate)
    if doi is not None:
        return resolve_root_paper(
            doi, openalex_client=openalex_client, crossref_client=crossref_client
        )

    raise TitleSearchRequired(candidate)
