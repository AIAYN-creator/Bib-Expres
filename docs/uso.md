# Uso

> El pipeline ya está conectado de principio a fin (DOI → expansión → BibTeX). Falta validarlo contra un caso real — ver el README para el estado actual del proyecto.

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
| `--weight-topic` | Peso del solapamiento temático en el score de relevancia | 1.0 |
| `--weight-citations` | Peso de las citas (normalizadas) en el score | 0.2 |
| `--weight-recency` | Peso de la recencia en el score | 0.1 |
| `--output` | Fichero de salida en formato BibTeX | `bibliografia.bib` |

El modo `similar` requiere tener configurada `SEMANTIC_SCHOLAR_API_KEY` (ver [instalación](instalacion.md)) — sin ella funciona igual, pero con un rate limit mucho más bajo (la CLI avisa si detecta esta combinación).

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
