# Uso

> [English version](en/usage.md) · Validado con casos reales: [v1](ejemplo.md), [v2](ejemplo-v2.md), [v3](ejemplo-v3.md).

## Uso básico

```bash
bib-expres --doi 10.1000/ejemplo --output bibliografia.bib
```

Dado un paper de partida, genera un fichero con la bibliografía consolidada a partir de él. También hay una [interfaz gráfica](instalacion.md#interfaz-gráfica) (`bib-expres-gui`), en español o inglés, para quien prefiera no usar la terminal.

## El paper de partida: `--doi` o `--input`

`--doi` es un atajo directo cuando ya sabes que es un DOI. `--input` acepta lo mismo más un ID o URL de arXiv, una ruta a un PDF o un título en texto libre, y detecta el tipo solo. Si el título es ambiguo (varios candidatos parecidos), la CLI pregunta cuál es el correcto; nunca elige uno por su cuenta.

```bash
bib-expres --input "2301.12345" --output bibliografia.bib                 # arXiv
bib-expres --input "./paper.pdf" --output bibliografia.bib                # PDF
bib-expres --input "Attention Is All You Need" --output bibliografia.bib  # título, con confirmación
```

**Límite conocido del ID de arXiv** (ver [ejemplo-v2.md](ejemplo-v2.md)): funciona resolviendo el DOI que arXiv asigna automáticamente al paper. Pero si ese paper se publicó después en una revista o congreso con su propio DOI (habitual en papers de ML conocidos; "Attention Is All You Need" es un ejemplo real), OpenAlex indexa el otro DOI como principal y la búsqueda por ID de arXiv falla con un mensaje que sugiere probar por título. Buscar por título no tiene este problema.

## Cómo elige los artículos (v3)

1. **Explora** el grafo de citas como siempre: de cada paper expandido, los `--max-fanout` candidatos más relevantes pasan a explorarse. Como mucho se expanden `--explore-budget` papers.
2. **Guarda todo lo que ve** y cuenta en cuántos de los papers explorados aparece cada candidato (sus **conexiones**).
3. **Elige al final** los mejores por un score que es la suma de tres señales, cada una explicable:
   - **relevancia temática**: tema, citas y recencia, la fórmula de siempre;
   - **conexiones**: "conectado con 5 papers de tu búsqueda";
   - **palabras clave** de OpenAlex en común con el paper de partida.

Los filtros (tipo, acceso abierto, idioma) se aplican al elegir, no al explorar: un paper que no quieres en el resultado puede seguir llevando a otros que sí. `--explain` enseña el desglose de los 20 primeros:

```
- A Survey on Vision Transformer
    0.67 = relevancia 0.64 (tema 0.56, citas 0.93, recencia 0.87) · conectado con 8 papers de la búsqueda · comparte: transformer models
```

Medido contra la bibliografía de tres revisiones publicadas, este método encuentra de media el **24 %** de lo que cita cada revisión entre sus 200 primeros resultados (v2: 9,9 %). Detalle en [ejemplo-v3.md](ejemplo-v3.md) y en `benchmarks/`.

## Parámetros

| Parámetro | Qué controla | Por defecto |
|---|---|---|
| `--doi` / `--input` | El paper de partida (uno de los dos es obligatorio) | — |
| `--generations` | Cuántos "saltos" desde el paper de partida (1-5) | 2 |
| `--max-articles` | Artículos en el resultado | 200 |
| `--max-fanout` | Candidatos que se exploran por cada paper | 20 |
| `--explore-budget` | Máximo de papers a expandir (acota el tiempo) | 30 |
| `--modes` | `references`, `citations`, `similar` (separados por coma) | `references,citations` |
| `--relevance-threshold` | Score final mínimo (0-1) para entrar en el resultado | 0.15 |
| `--weight-topic` / `--weight-citations` / `--weight-recency` | Pesos dentro de la relevancia temática | 1.0 / 0.2 / 0.1 |
| `--weight-coupling` | Peso de las conexiones en el score final | 1.0 |
| `--weight-keywords` | Peso de las palabras clave en común | 0.5 |
| `--explain` | Mostrar el desglose del score de los 20 primeros (en `stderr`) | desactivado |
| `--doc-types` | Tipos de documento permitidos, separados por coma (p.ej. `article,preprint`; vocabulario de OpenAlex) | todos |
| `--open-access-only` | Solo artículos de acceso abierto | desactivado |
| `--language` | `any` (cualquiera), `same` (el del paper de partida) o códigos ISO como `es,en` | `any` |
| `--library-link` | Enlace de acceso remoto de tu biblioteca ([guía](acceso-institucional.md)) | `LIBRARY_LINK_TEMPLATE` del `.env` |
| `--publishers` | Editoriales que cubre tu institución, separadas por `;` | `SUBSCRIBED_PUBLISHERS` del `.env` |
| `--accessible-only` | Quitar lo que no puedes leer (ni abierto ni de una editorial marcada) | desactivado |
| `--strict-access` | Con `--accessible-only`, quitar también lo que no se puede comprobar | desactivado |
| `--output` | Fichero de salida | `bibliografia.bib` |
| `--format` | `bibtex`, `ris`, `csljson` o `xlsx` | según la extensión de `--output`, o `bibtex` |
| `--quiet` | Sin línea de progreso ni resumen de cuota | desactivado |

El paper de partida nunca se descarta, ni por relevancia ni por ningún filtro: siempre aparece en el resultado. Los artículos sin idioma conocido no se descartan por el filtro de idioma.

El modo `similar` funciona mejor con `SEMANTIC_SCHOLAR_API_KEY` configurada (ver [instalación](instalacion.md)). Sin ella va con un límite de peticiones mucho más bajo, y la CLI avisa.

## Ejemplos

Búsqueda más amplia:

```bash
bib-expres --doi 10.1000/ejemplo --generations 3 --max-articles 500 \
  --modes references,citations,similar --output bibliografia-amplia.bib
```

Solo en español, partiendo de un paper en español:

```bash
bib-expres --doi 10.6018/analesps.30.3.199361 --language same --output revision.xlsx
```

Solo lo que puedes leer, con enlaces a través de tu biblioteca:

```bash
bib-expres --doi 10.1000/ejemplo --publishers "Elsevier BV;Springer Nature" \
  --accessible-only --library-link "https://proxy.tu-uni.es/login?url=" --output revision.xlsx
```

## Salida

BibTeX (`.bib`), RIS (`.ris`), CSL-JSON (`.json`) o Excel (`.xlsx`), según `--format` o la extensión de `--output`. Los tres primeros se importan directamente en Zotero, Mendeley, JabRef o LaTeX.

### Excel, para revisiones bibliográficas

Una fila por artículo, pensada para la primera ronda de una revisión:

| Columna | Contenido |
|---|---|
| Título | título del artículo |
| Autores | todos, separados por `; `, en el orden del artículo |
| DOI | el DOI como enlace a `doi.org` (o a la ficha de OpenAlex si no tiene DOI) |
| Tema | tema principal según OpenAlex |
| Palabras clave | palabras clave según OpenAlex |
| Relevancia | el score final (0–1), como número para ordenar |
| Por qué | el desglose del score en una línea |
| Acceso | abierto, abierto (bronze), institución, sin acceso conocido o no comprobado ([guía](acceso-institucional.md)) |
| Enlace de acceso | la versión libre, o el enlace a través de tu biblioteca |
| Otras notas | vacía, para tus anotaciones |

Cabecera fija y autofiltro: ordenar por autor o por relevancia, o filtrar por tema, es un clic. Desde la GUI, las cabeceras salen en el idioma de la interfaz.

El fichero queda en la ruta de `--output` (o en `bibliografia.bib`, en la carpeta desde la que ejecutaste el comando). El programa no lo abre ni lo mueve.

## Progreso y cuota

Mientras busca, la CLI muestra en `stderr` una línea que se reescribe sobre sí misma:

```
explorados 5/21 -- 480 candidatos -- generacion 2 -- Effective Approaches to Attention-based Neu
```

Al terminar imprime cuánta **cuota de OpenAlex** queda hoy:

```
Cuota de OpenAlex hoy: 482/1000 peticiones (~6 busquedas) -- se reinicia en 23 h 28 min
```

OpenAlex da gratis unas **1.000 peticiones al día** y una búsqueda por defecto gasta unas 75, así que salen unas **13 búsquedas nuevas al día**. Repetir una búsqueda ya hecha no gasta nada, porque sale de la caché local (una semana). Si la cuota se agota, bib_exprés avisa con un mensaje claro y dice cuánto esperar, en vez de quedarse colgado. `--quiet` oculta la línea de progreso y la de cuota; `stdout` queda solo para el resultado.

En la GUI, lo mismo se ve como barra de progreso con Cancelar y, en la cabecera, *"≈ 6 de 13 búsquedas hoy"* ([detalle](instalacion.md#interfaz-gráfica)).

## Rendimiento

Una búsqueda por defecto desde *Attention Is All You Need* tarda **~55 s con la caché vacía** (74 peticiones a OpenAlex) y un par de segundos si ya está en caché. v3 tarda más que v2 (~36 s) porque explora todo antes de elegir; a cambio encuentra unas 2,4 veces más bibliografía relevante. El tiempo depende sobre todo de lo rápido que responda OpenAlex ese día y del tamaño del grafo de citas del paper de partida. La primera validación, de v1, está en [ejemplo.md](ejemplo.md).
