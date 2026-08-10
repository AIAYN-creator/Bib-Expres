from __future__ import annotations

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
