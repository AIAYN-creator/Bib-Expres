# Uso

> Validado de principio a fin contra un caso real — ver [docs/ejemplo.md](ejemplo.md).

## Uso básico

```bash
bib-expres --doi 10.1000/ejemplo --output bibliografia.bib
```

Dado un paper padre, genera un fichero con la bibliografía consolidada a partir de ese paper. También hay una [interfaz gráfica](instalacion.md#interfaz-gráfica) (`bib-expres-gui`) para quien prefiera no usar la CLI.

## El paper padre: `--doi` o `--input`

`--doi` es un atajo directo cuando ya sabes que es un DOI. `--input` acepta lo mismo más ID/URL de arXiv, una ruta a un PDF, o un título en texto libre — detecta el tipo solo. Si el título es ambiguo (varios candidatos parecidos), la CLI pregunta interactivamente cuál es el correcto; nunca elige uno por su cuenta.

```bash
bib-expres --input "2301.12345" --output bibliografia.bib          # arXiv
bib-expres --input "./paper.pdf" --output bibliografia.bib         # PDF
bib-expres --input "Attention Is All You Need" --output bibliografia.bib  # titulo, con confirmacion
```

**Límite conocido del ID de arXiv** (confirmado con datos reales, ver [docs/ejemplo-v2.md](ejemplo-v2.md)): funciona resolviendo el DOI que arXiv asigna automáticamente al paper, pero si ese paper se publicó después en una revista o conferencia con su propio DOI (habitual en papers de ML conocidos — "Attention Is All You Need" es un ejemplo real), OpenAlex indexa el otro DOI como principal y la búsqueda por ID de arXiv falla con un mensaje que sugiere probar por título. Buscar por título, como en el tercer ejemplo de arriba, no tiene este problema.

## Parámetros configurables

| Parámetro | Qué controla | Valor por defecto |
|---|---|---|
| `--doi` / `--input` | El paper padre del que partir (uno de los dos es obligatorio) | — |
| `--generations` | Cuántos "saltos" de expansión desde el paper padre (1-5) | 2 |
| `--max-articles` | Tope total de artículos en la bibliografía final | 200 |
| `--max-fanout` | Tope de artículos nuevos a traer por cada paper individual | 20 |
| `--modes` | Modos de expansión activos: `references`, `citations`, `similar` (separados por coma) | `references,citations` |
| `--relevance-threshold` | Puntuación mínima (0-1) para que un artículo se incluya | 0.3 |
| `--weight-topic` | Peso del solapamiento temático en el score de relevancia | 1.0 |
| `--weight-citations` | Peso de las citas (normalizadas) en el score | 0.2 |
| `--weight-recency` | Peso de la recencia en el score | 0.1 |
| `--doc-types` | Tipos de documento permitidos, separados por coma (p.ej. `article,preprint`) — vocabulario de OpenAlex, sin curar | todos |
| `--open-access-only` | Solo incluir artículos de acceso abierto | desactivado |
| `--output` | Fichero de salida | `bibliografia.bib` |
| `--format` | Formato de salida: `bibtex`, `ris` o `csljson` | se infiere de la extensión de `--output`, o `bibtex` |

`--doc-types` y `--open-access-only` no afectan al paper padre — este nunca se descarta (ni por relevancia, ni por tipo, ni por acceso abierto), siempre aparece en el resultado. Confirmado con datos reales en [docs/ejemplo-v2.md](ejemplo-v2.md).

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

BibTeX (`.bib`), RIS (`.ris`) o CSL-JSON (`.json`), según `--format` o la extensión de `--output`. Los tres son estándares, importables directamente en Zotero, Mendeley, JabRef o LaTeX (`\bibliography{...}` para BibTeX).

**Dónde encontrarlo al terminar**: en la ruta que le des a `--output`, o en `bibliografia.bib` dentro del directorio desde el que ejecutaste el comando si no lo especificas. El programa no lo abre ni lo mueve a ningún sitio — simplemente ahí queda, esperando a que lo cojas (para importarlo en tu gestor de referencias, subirlo a otro sitio, lo que necesites).

## Rendimiento

En la validación real documentada en [docs/ejemplo.md](ejemplo.md): **200 artículos en ~22 segundos**, con los parámetros por defecto (2 generaciones, tope de 200, modos `references,citations`) sobre un paper con miles de citas entrantes. El tiempo depende sobre todo del tamaño del grafo de citas del paper padre y de cuántas generaciones/artículos pidas — no es una cifra fija, pero da una idea de la escala.
