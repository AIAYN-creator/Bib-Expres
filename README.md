# bib_exprés

Herramienta de snowballing bibliográfico: a partir de un paper padre (DOI), expande generaciones de referencias, citas y artículos similares, y consolida una bibliografía filtrada por relevancia.

**Estado: v1 funciona de principio a fin — 200 artículos en ~22 segundos** en la validación real ([ver ejemplo](docs/ejemplo.md)). **v2 también funciona de principio a fin** — GUI, curación tipo Tinder, `.exe` standalone, entrada por arXiv/título/PDF, RIS/CSL-JSON y filtros, validado tanto contra datos reales como con clics reales dentro de la ventana ([ver ejemplo de v2](docs/ejemplo-v2.md)). **[Descarga directa del `.exe` en Releases](https://github.com/AIAYN-creator/Bib-Expres/releases/latest)** — sin instalar Python.

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

Todos los parámetros de la búsqueda son configurables (generaciones, tope total de artículos, tope por artículo, modos de expansión activos, pesos de relevancia, filtros por tipo de documento/acceso abierto) — nada queda fijo en el código. Se maneja desde la CLI o desde la interfaz gráfica de escritorio, a elegir.

## Fuentes de datos

- **OpenAlex** (primaria) — referencias, citas, temas/conceptos. Sin API key.
- **Semantic Scholar** (complemento) — artículos similares. Requiere API key gratuita.
- **CrossRef** — resolución y verificación de DOI.

## Instalación

```bash
pip install -e ".[dev]"
```

Guía completa, con configuración de `.env`: [docs/instalacion.md](docs/instalacion.md).

## Uso

Por CLI:

```bash
bib-expres --doi 10.1000/ejemplo --output bibliografia.bib
```

Referencia completa de parámetros: [docs/uso.md](docs/uso.md).

Por interfaz gráfica (sin terminal, DOI/arXiv/título/PDF como entrada):

```bash
bib-expres-gui
```

O, sin tener Python instalado en la máquina que la vaya a usar: **[descarga `bib-expres-gui.exe` directamente de Releases](https://github.com/AIAYN-creator/Bib-Expres/releases/latest)** (~15 MB) y ejecútalo — ese enlace siempre apunta a la última versión publicada. También se puede construir en local con `pip install -e ".[packaging]"` seguido de `pyinstaller packaging/bib-expres-gui.spec`. Detalles en [docs/instalacion.md](docs/instalacion.md).

## Trabajos relacionados

bib_exprés no es la primera herramienta para explorar bibliografía a partir de un paper. Algunas referencias del mismo espacio:

- **[Connected Papers](https://www.connectedpapers.com/)** — explorador visual: a partir de un paper, dibuja un grafo de artículos relacionados por co-citación. Pensado para explorar visualmente, no para generar una bibliografía exportable con reglas configurables.
- **[ResearchRabbit](https://www.researchrabbit.ai/)** — similar en espíritu ("Spotify para papers"), con colecciones y descubrimiento por similitud/citas, también centrado en exploración visual interactiva.
- **[Litmaps](https://www.litmaps.com/)** — mapea cómo evoluciona una red de citas en el tiempo, orientado a mantener revisiones de literatura actualizadas.
- **[ASReview](https://asreview.nl/)** — open-source, pero resuelve un problema distinto: dado un conjunto grande de candidatos (p.ej. exportado de una base de datos), ayuda a priorizar cuáles cribar primero para una revisión sistemática, usando aprendizaje activo.

La diferencia de bib_exprés: es una herramienta de línea de comandos, librería y app de escritorio (no una app web), con un algoritmo de expansión y relevancia configurable y transparente, cuya salida es directamente un fichero de bibliografía (BibTeX, RIS o CSL-JSON) listo para un gestor de referencias o LaTeX — no un grafo visual para explorar a mano.

## Limitaciones

- Solo encuentra lo que **OpenAlex, Semantic Scholar o CrossRef** tengan indexado — papers muy nuevos, muy de nicho, o fuera de esas bases no van a aparecer.
- La bibliografía es siempre un **subconjunto acotado** (por generaciones y tope de artículos), no "todo lo relacionado" — es una decisión consciente (rendimiento y respeto a las APIs), no un descuido.
- El modo "similares" depende de tener configurada una API key de Semantic Scholar — sin ella, la expansión se queda solo con el grafo de citas de OpenAlex.
- El score de relevancia es una **fórmula simple y transparente**, no un modelo de lenguaje ni embeddings — prioriza poder explicar por qué algo entra o no, a costa de ser menos sofisticado que un enfoque de ML.
- El `.exe` no está firmado — Windows puede mostrar un aviso de SmartScreen la primera vez ("Más información" > "Ejecutar de todas formas"), y el antivirus puede bloquearlo brevemente nada más construirlo (visto de verdad al generar el build, no solo en teoría).
- Buscar el paper padre por ID de arXiv falla si ese paper se publicó después en otro sitio con su propio DOI (le pasa a bastantes papers de ML conocidos) — buscarlo por título no tiene este problema. Detalle en [docs/ejemplo-v2.md](docs/ejemplo-v2.md).
- El paper padre nunca se descarta por los filtros de tipo de documento/acceso abierto (tampoco por relevancia) — siempre aparece en el resultado final, sea cual sea el filtro pedido.

## Qué queda para v2

**v2 está cerrado** — [release `v2.0.0`](https://github.com/AIAYN-creator/Bib-Expres/releases/tag/v2.0.0), hecho, validado contra datos reales, probado a mano dentro de la ventana, y publicado como descarga directa:

- Interfaz gráfica de escritorio (`bib-expres-gui`) y empaquetado como `.exe` standalone — descargable, no solo "clona y construye".
- Curación de resultados tipo Tinder: revisar cada candidato (abstract) y decidir guardar/descartar a mano.
- Formatos de entrada adicionales: ID/URL de arXiv, título en texto libre, PDF.
- Formatos de salida adicionales: RIS y CSL-JSON, además de BibTeX.
- Filtros por tipo de documento y estado de acceso abierto.

**Descartado por ahora:** autenticación/autorización — solo tendría sentido si esto se expusiera como servicio a terceros, y v2 sigue siendo una app de escritorio local.

## v2.1.0 — parche de seguridad: DOIs sin escapar en las peticiones HTTP

Una auditoría de seguridad encontró que `bib_exprés` metía el DOI directamente en el path de la URL al pedir metadata a OpenAlex, CrossRef y Semantic Scholar, sin escapar caracteres especiales. El problema: un DOI válido puede contener `/`, `:`, `;`, `(` y `)` — los mismos caracteres que delimitan un path HTTP — así que un DOI pensado para manipular la ruta podía alterar la petición real enviada a esas APIs en vez de limitarse a identificar un paper. El caso más delicado estaba en el modo "similares": el DOI de cada candidato viene tal cual de la respuesta de Semantic Scholar (una fuente externa), sin pasar por ninguna validación local, antes de usarse para pedir ese paper a OpenAlex.

**Arreglado**: los cuatro sitios donde un DOI (o el ID interno de OpenAlex de un paper) se interpolaba en el path de una petición ahora lo escapan primero (`urllib.parse.quote`). Se comprobó contra las tres APIs reales que un DOI normal con `/` se sigue resolviendo exactamente igual que antes del parche — el arreglo no cambia nada del comportamiento habitual, solo cierra la vía para manipular la ruta.

No hace falta ninguna acción manual: actualizar a esta versión (o al `.exe` publicado en Releases) ya incluye el parche, sin cambios de configuración ni de comportamiento visible.

## v2.1.1 — icono propio para `bib-expres-gui.exe`

El `.exe` de la GUI salía con el icono genérico de PyInstaller: el `.spec` no declaraba ninguno, y el único parámetro de icono de `pywebview` (`webview.start(icon=...)`) solo funciona en GTK/QT, no hace nada en Windows.

Se añadió `packaging/icon.ico` (nodo raíz ramificándose en tres — el snowballing de citas que hace la app) referenciado desde `EXE(icon=...)` en `packaging/bib-expres-gui.spec`. Sin cambios de comportamiento: solo el icono en Explorador, menú Inicio, barra de tareas y la propia ventana.

## Qué queda para v3

Todavía sin planificar en detalle — apuntado aquí como idea, igual que empezó v2:

- **Filtro por idioma** — solo artículos en español, o en todos (al estilo Google Scholar). OpenAlex ya devuelve el idioma de cada artículo en sus respuestas (`language`, código ISO como `en`/`es` — comprobado en directo), así que el dato está disponible en la fuente, pero `bib_exprés` no lo guarda ni lo filtra todavía.
- **Interfaz gráfica en inglés o castellano, a elegir** — hoy todos los textos de la GUI (`gui/static/`) están fijos en español.

## Preguntas abiertas

- Los valores por defecto (`max_articles=200`, `max_fanout_per_node=20`, pesos de relevancia) son un punto de partida razonable, no un número validado — probablemente haga falta ajustarlos con casos reales.
- Si compensa firmar el `.exe` en algún momento (certificado de firma de código) para que Windows deje de avisar — de momento se acepta el aviso de SmartScreen como coste conocido.
- Si el proyecto crece más allá de un uso personal/de equipo, falta decidir cómo se distribuye la parte de librería/CLI (¿PyPI? ¿solo instalación desde GitHub?).

## Licencia

MIT — ver [LICENSE](LICENSE).
