"""Comprobaciones de la GUI estatica que no necesitan navegador: que los dos
idiomas tengan las mismas claves, que todo texto del HTML exista en ellos, y
que todo id que usa app.js exista en index.html."""

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "src" / "bib_expres" / "gui" / "static"


def _language_block(source: str, lang: str) -> str:
    start = source.index(f"  {lang}: {{")
    end = source.index("\n  },", start)
    return source[start:end]


def _keys(block: str) -> set[str]:
    # Una clave va al principio de linea o justo despues del valor anterior ("...", )
    # y antes de su propio valor entre comillas; asi no cuentan los "Texto: ..." internos.
    return set(re.findall(r'(?:^\s+|",\s*)([A-Za-z_][A-Za-z0-9_]*):\s*"', block, re.M))


def test_es_and_en_have_the_same_keys():
    source = (STATIC / "i18n.js").read_text(encoding="utf-8")
    es, en = _keys(_language_block(source, "es")), _keys(_language_block(source, "en"))
    # Los err_* propios del ingles existen porque en espanol se muestra el detalle del backend
    assert es - en == set()
    assert {k for k in en - es if not k.startswith("err_")} == set()


def test_every_html_text_key_is_translated():
    source = (STATIC / "i18n.js").read_text(encoding="utf-8")
    es, en = _keys(_language_block(source, "es")), _keys(_language_block(source, "en"))
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    used = set(re.findall(r'data-i(?:-ph)?="([^"]+)"', html))
    assert used - es == set()
    assert used - en == set()


def test_every_id_used_in_app_js_exists_in_html():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    ids = set(re.findall(r'id="([^"]+)"', html))
    used = set(re.findall(r'\$\("([^"]+)"\)', js))
    assert used and used - ids == set()


def test_logo_is_bundled_with_the_gui():
    assert (STATIC / "logo.png").stat().st_size > 1000


def test_content_security_policy_blocks_remote_and_inline():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', html).group(1)
    assert "default-src 'none'" in csp
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp
    # y la pagina no depende de nada inline que la CSP bloquearia
    assert not re.search(r"<script>(?!\s*</script>)|\son[a-z]+=|style=\"", html)
