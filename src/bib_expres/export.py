from __future__ import annotations

import re

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
