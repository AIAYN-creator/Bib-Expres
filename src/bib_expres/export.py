from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Paper


def _cite_key(paper: Paper, used_keys: set[str]) -> str:
    if paper.authors:
        last_name = paper.authors[0].split()[-1]
    else:
        last_name = "unknown"
    last_name = re.sub(r"[^a-zA-Z]", "", last_name).lower() or "unknown"
    year = str(paper.year) if paper.year else "nd"

    base = f"{last_name}{year}"
    key = base
    suffix = 0
    while key in used_keys:
        key = f"{base}{chr(ord('a') + suffix)}"
        suffix += 1
    used_keys.add(key)
    return key


_ESCAPE_MAP = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
}


def _escape(value: str) -> str:
    """Caracter a caracter sobre el original -- si se hiciera en pasadas
    secuenciales de str.replace(), escapar '\\' despues de '{'/'}' (o viceversa)
    reescaparia las llaves que la propia sustitucion introduce."""
    return "".join(_ESCAPE_MAP.get(ch, ch) for ch in value)


def _entry(paper: Paper, key: str) -> str:
    fields = {
        "title": _escape(paper.title),
        "author": " and ".join(paper.authors) if paper.authors else "Unknown",
        "year": str(paper.year) if paper.year else "",
        "journal": _escape(paper.venue) if paper.venue else "",
    }
    if paper.doi:
        fields["doi"] = paper.doi
        fields["url"] = f"https://doi.org/{paper.doi}"

    lines = [f"@article{{{key},"]
    for name, value in fields.items():
        if value:
            lines.append(f"  {name} = {{{value}}},")
    lines.append("}")
    return "\n".join(lines)


def to_bibtex(papers: list[Paper]) -> str:
    """Todas las entradas salen como @article -- simplificacion consciente para
    v1, no se modela el tipo de documento con precision todavia."""
    used_keys: set[str] = set()
    entries = [_entry(paper, _cite_key(paper, used_keys)) for paper in papers]
    return "\n\n".join(entries) + "\n" if entries else ""


def write_bibtex(papers: list[Paper], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_bibtex(papers))


def _ris_entry(paper: Paper) -> str:
    lines = ["TY  - JOUR", f"TI  - {paper.title}"]
    for author in paper.authors:
        lines.append(f"AU  - {author}")
    if paper.year:
        lines.append(f"PY  - {paper.year}")
    if paper.venue:
        lines.append(f"T2  - {paper.venue}")
    if paper.doi:
        lines.append(f"DO  - {paper.doi}")
        lines.append(f"UR  - https://doi.org/{paper.doi}")
    lines.append("ER  -")
    return "\n".join(lines)


def to_ris(papers: list[Paper]) -> str:
    """TY fijo a JOUR -- misma simplificacion consciente que @article en to_bibtex,
    no se modela el tipo de documento con precision todavia."""
    return "\n\n".join(_ris_entry(p) for p in papers) + "\n" if papers else ""


def write_ris(papers: list[Paper], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_ris(papers))


def _split_name(author: str) -> dict[str, str]:
    """Ultima palabra = apellido, resto = nombre -- mismo riesgo de nombres
    compuestos que ya asume _cite_key con authors[0].split()[-1]."""
    parts = author.split()
    if len(parts) <= 1:
        return {"family": author, "given": ""}
    return {"family": parts[-1], "given": " ".join(parts[:-1])}


def _csljson_entry(paper: Paper, key: str) -> dict:
    entry: dict = {
        "id": key,
        "type": "article-journal",
        "title": paper.title,
        "author": [_split_name(a) for a in paper.authors],
    }
    if paper.year:
        entry["issued"] = {"date-parts": [[paper.year]]}
    if paper.venue:
        entry["container-title"] = paper.venue
    if paper.doi:
        entry["DOI"] = paper.doi
        entry["URL"] = f"https://doi.org/{paper.doi}"
    return entry


def to_csljson(papers: list[Paper]) -> str:
    """type fijo a article-journal -- misma simplificacion consciente que @article
    en to_bibtex."""
    used_keys: set[str] = set()
    entries = [_csljson_entry(p, _cite_key(p, used_keys)) for p in papers]
    return json.dumps(entries, indent=2, ensure_ascii=False)


def write_csljson(papers: list[Paper], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_csljson(papers))


EXPORTERS = {"bibtex": write_bibtex, "ris": write_ris, "csljson": write_csljson}
_FORMAT_BY_EXTENSION = {".bib": "bibtex", ".ris": "ris", ".json": "csljson"}


def infer_format(output_path: str) -> str:
    """Extension de --output -> formato; BibTeX si la extension no se reconoce,
    para no romper el comportamiento por defecto de quien no toque el flag nuevo."""
    return _FORMAT_BY_EXTENSION.get(Path(output_path).suffix.lower(), "bibtex")


def write(papers: list[Paper], path: str, format: str = "bibtex") -> None:
    try:
        exporter = EXPORTERS[format]
    except KeyError:
        valid = ", ".join(EXPORTERS)
        raise ValueError(f"formato desconocido '{format}' -- validos: {valid}") from None
    exporter(papers, path)
