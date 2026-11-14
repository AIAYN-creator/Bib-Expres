from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

from .access import access_label, is_openable_url
from .models import Paper
from .relevance import explain


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


XLSX_COLUMNS = [
    # (cabecera es, cabecera en, ancho aproximado en caracteres)
    ("Título", "Title", 60),
    ("Autores", "Authors", 35),
    ("DOI", "DOI", 28),
    ("Tema", "Topic", 30),
    ("Palabras clave", "Keywords", 40),
    ("Relevancia", "Relevance", 11),
    ("Por qué", "Why", 60),
    ("Acceso", "Access", 22),
    ("Enlace de acceso", "Access link", 30),
    ("Otras notas", "Other notes", 45),
]


def _paper_url(paper: Paper) -> str | None:
    """Enlace al paper: el DOI si lo hay; si no, su ficha en OpenAlex. El DOI
    viene de una API externa -- se escapa para que no pueda alterar la URL."""
    if paper.doi:
        return "https://doi.org/" + quote(paper.doi, safe="/")
    if paper.openalex_id:
        return "https://openalex.org/" + quote(paper.openalex_id, safe="")
    return None


def write_xlsx(papers: list[Paper], path: str, lang: str = "es") -> None:
    """Hoja para la primera ronda de una revision bibliografica: una fila por
    paper, con columna libre para notas. Todo texto se fuerza a tipo texto: openpyxl
    trataria como formula un titulo que empiece por '=' (inyeccion de formulas)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Bibliography" if lang == "en" else "Bibliografía"

    for col, (header_es, header_en, width) in enumerate(XLSX_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col, value=header_en if lang == "en" else header_es)
        cell.font = Font(bold=True)
        ws.column_dimensions[get_column_letter(col)].width = width

    def text_cell(row: int, col: int, value: str | None):
        cell = ws.cell(row=row, column=col)
        if value:
            cell.value = value
            cell.data_type = "s"
        return cell

    for row, paper in enumerate(papers, start=2):
        text_cell(row, 1, paper.title)
        text_cell(row, 2, "; ".join(paper.authors))

        url = _paper_url(paper)
        doi_cell = text_cell(row, 3, paper.doi or ("OpenAlex " + paper.openalex_id if url else None))
        if url:
            doi_cell.hyperlink = url
            doi_cell.style = "Hyperlink"

        text_cell(row, 4, paper.topic)
        text_cell(row, 5, "; ".join(paper.keywords))

        if paper.relevance_score is not None:
            score_cell = ws.cell(row=row, column=6, value=round(paper.relevance_score, 3))
            score_cell.number_format = "0.00"

        text_cell(row, 7, explain(paper.score_breakdown, lang))
        if paper.access_status:
            text_cell(row, 8, access_label(paper.access_status, lang) or paper.access_status)
        if is_openable_url(paper.access_url):
            link_cell = text_cell(row, 9, "open" if lang == "en" else "abrir")
            link_cell.hyperlink = paper.access_url
            link_cell.style = "Hyperlink"

        notes = ws.cell(row=row, column=10)
        notes.alignment = Alignment(wrap_text=True, vertical="top")

    ws.freeze_panes = "A2"
    last_col = get_column_letter(len(XLSX_COLUMNS))
    ws.auto_filter.ref = f"A1:{last_col}{max(len(papers) + 1, 1)}"
    wb.save(path)


EXPORTERS = {
    "bibtex": write_bibtex,
    "ris": write_ris,
    "csljson": write_csljson,
    "xlsx": write_xlsx,
}
_FORMAT_BY_EXTENSION = {".bib": "bibtex", ".ris": "ris", ".json": "csljson", ".xlsx": "xlsx"}


def infer_format(output_path: str) -> str:
    """Extension de --output -> formato; BibTeX si la extension no se reconoce,
    para no romper el comportamiento por defecto de quien no toque el flag nuevo."""
    return _FORMAT_BY_EXTENSION.get(Path(output_path).suffix.lower(), "bibtex")


def write(papers: list[Paper], path: str, format: str = "bibtex", lang: str = "es") -> None:
    """`lang` solo afecta a los formatos con texto para personas (el Excel); los
    de bibliografia (BibTeX, RIS, CSL-JSON) no tienen textos que traducir."""
    try:
        exporter = EXPORTERS[format]
    except KeyError:
        valid = ", ".join(EXPORTERS)
        raise ValueError(f"formato desconocido '{format}' -- validos: {valid}") from None
    if format == "xlsx":
        exporter(papers, path, lang=lang)
    else:
        exporter(papers, path)
