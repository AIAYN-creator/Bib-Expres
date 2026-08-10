# Uso

> Esta página describe la interfaz **objetivo**, tal como está definida en la arquitectura del proyecto. La CLI se está implementando por partes — no todo lo de aquí funciona todavía. Consulta el README para el estado actual.

## Uso básico

```bash
bib-expres --doi 10.1000/ejemplo --output bibliografia.bib
```

Dado un DOI, genera un fichero BibTeX con la bibliografía consolidada a partir de ese paper.

## Parámetros configurables

| Parámetro | Qué controla | Valor por defecto |
|---|---|---|
| `--doi` | El paper padre del que partir (obligatorio) | — |
| `--generations` | Cuántos "saltos" de expansión desde el paper padre (1-5) | 2 |
| `--max-articles` | Tope total de artículos en la bibliografía final | 200 |
| `--max-fanout` | Tope de artículos nuevos a traer por cada paper individual | 20 |
| `--modes` | Modos de expansión activos: `references`, `citations`, `similar` (separados por coma) | `references,citations` |
| `--relevance-threshold` | Puntuación mínima (0-1) para que un artículo se incluya | 0.3 |
| `--output` | Fichero de salida en formato BibTeX | — |

El modo `similar` requiere tener configurada `SEMANTIC_SCHOLAR_API_KEY` (ver [instalación](instalacion.md)).

## Ejemplo con parámetros ajustados

```bash
bib-expres --doi 10.1000/ejemplo \
  --generations 3 \
  --max-articles 500 \
  --modes references,citations,similar \
  --output bibliografia-amplia.bib
```

## Salida

Un fichero `.bib` estándar, importable directamente en Zotero, Mendeley, JabRef o LaTeX (`\bibliography{...}`).
