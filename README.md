# bib_exprés

Herramienta de snowballing bibliográfico: a partir de un paper padre (DOI), expande generaciones de referencias, citas y artículos similares, y consolida una bibliografía filtrada por relevancia.

**Estado: arquitectura definida, implementación en curso.**

## Cómo funciona

```
DOI de entrada
  -> resolucion (CrossRef + OpenAlex)          -> paper raiz
  -> expansion (cola por prioridad)
       -> OpenAlex: referencias + citas
       -> Semantic Scholar: articulos similares (modo opcional)
       -> puntuacion de relevancia + deduplicacion en cada candidato
     ... hasta agotar generaciones, tope de articulos, o el grafo
  -> exportacion -> fichero .bib
```

Todos los parámetros de la búsqueda son configurables (generaciones, tope total de artículos, tope por artículo, modos de expansión activos, pesos de relevancia) — nada queda fijo en el código.

## Fuentes de datos

- **OpenAlex** (primaria) — referencias, citas, temas/conceptos. Sin API key.
- **Semantic Scholar** (complemento) — artículos similares. Requiere API key gratuita.
- **CrossRef** — resolución y verificación de DOI.

## Instalación (modo desarrollo)

```bash
pip install -e ".[dev]"
```

Copia `.env.example` a `.env` y rellena tu email de contacto y, opcionalmente, tu API key de Semantic Scholar.

## Uso

```bash
bib-expres --version
```

(el pipeline completo todavía se está implementando)

## Licencia

MIT — ver [LICENSE](LICENSE).
