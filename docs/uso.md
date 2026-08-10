# Uso

> Validado de principio a fin contra un caso real — ver [docs/ejemplo.md](ejemplo.md).

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

**Dónde encontrarlo al terminar**: en la ruta que le des a `--output`, o en `bibliografia.bib` dentro del directorio desde el que ejecutaste el comando si no lo especificas. El programa no lo abre ni lo mueve a ningún sitio — simplemente ahí queda, esperando a que lo cojas (para importarlo en tu gestor de referencias, subirlo a otro sitio, lo que necesites).

## Rendimiento

En la validación real documentada en [docs/ejemplo.md](ejemplo.md): **200 artículos en ~22 segundos**, con los parámetros por defecto (2 generaciones, tope de 200, modos `references,citations`) sobre un paper con miles de citas entrantes. El tiempo depende sobre todo del tamaño del grafo de citas del paper padre y de cuántas generaciones/artículos pidas — no es una cifra fija, pero da una idea de la escala.
