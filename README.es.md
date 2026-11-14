<div align="center">

<img src="packaging/icon.png" width="120" alt="Logo de bib-exprés: un nodo raíz ramificándose en tres">

# bib_exprés

**De un paper a tu bibliografía, sin cajas negras.**

[English](README.md) · **Español**

[![Última versión](https://img.shields.io/github/v/release/AIAYN-creator/Bib-Expres?label=descarga)](https://github.com/AIAYN-creator/Bib-Expres/releases/latest)
[![Licencia MIT](https://img.shields.io/badge/licencia-MIT-blue)](LICENSE)

</div>

## Qué hace

Le das **un paper** (DOI, arXiv, título o el propio PDF) y bib_exprés hace *snowballing* por ti. Sigue sus referencias, los papers que lo citan y los artículos similares, generación tras generación, puntúa cada candidato con una fórmula de relevancia **sencilla y a la vista**, y te entrega una bibliografía lista para Zotero, LaTeX o Excel.

```
paper de entrada
  -> resolución (CrossRef + OpenAlex)          -> paper raíz
  -> expansión (cola por prioridad)
       -> OpenAlex: referencias + citas
       -> Semantic Scholar: artículos similares (opcional)
       -> puntuación de relevancia + deduplicación de cada candidato
     ... hasta agotar generaciones, el tope de artículos o el grafo
  -> curación opcional (guardar / descartar uno a uno)
  -> exportación -> .bib / .ris / .json / .xlsx
```

## Rendimiento

**200 artículos en ~22 segundos**, partiendo de *Attention Is All You Need* con los parámetros por defecto (2 generaciones, referencias + citas). Es una ejecución real, no una estimación: [ver el ejemplo completo](docs/ejemplo.md). El tiempo depende sobre todo de lo rápido que responda OpenAlex ese día: la misma búsqueda, repetida en noviembre de 2026 con la caché vacía, tardó entre 27 y 39 s.

## Descarga y uso

### Sin instalar nada (Windows)

**[Descarga `bib-expres-gui.exe` de Releases](https://github.com/AIAYN-creator/Bib-Expres/releases/latest)** (~17 MB) y ejecútalo. No hace falta Python. Ese enlace apunta siempre a la última versión, y cada release publica el SHA-256 del `.exe` para comprobar la descarga.

Windows puede avisar la primera vez porque el `.exe` no está firmado ("Más información" > "Ejecutar de todas formas").

### Con Python

```bash
pip install -e ".[dev]"
```

Interfaz gráfica:

```bash
bib-expres-gui
```

Línea de comandos:

```bash
bib-expres --doi 10.1000/ejemplo --output bibliografia.bib
bib-expres --input "Attention Is All You Need" --output revision.xlsx
```

Guías completas: [instalación y `.env`](docs/instalacion.md) · [todos los parámetros](docs/uso.md).

## Funcionalidades

- **Entrada**: DOI, ID o URL de arXiv, título en texto libre (eliges entre los candidatos) o un PDF.
- **Expansión configurable**: generaciones, tope total, tope por artículo, modos (referencias / citas / similares) y pesos de relevancia. Nada queda fijo en el código.
- **Filtros**: tipo de documento y acceso abierto.
- **Curación tipo Tinder**: revisa cada candidato con su abstract y decide guardar o descartar con botones, flechas o arrastrando.
- **Progreso en directo**: barra, paper que se está explorando, "última actividad hace X s" y botón para cancelar quedándote con lo encontrado.
- **Salida**: BibTeX, RIS, CSL-JSON y **Excel** para revisiones bibliográficas (título, autores, DOI enlazado, tema, palabras clave, relevancia y una columna libre para notas).

## Fuentes de datos

- **OpenAlex** (primaria): referencias, citas, temas y palabras clave. Sin API key.
- **Semantic Scholar** (complemento): artículos similares. Requiere API key gratuita.
- **CrossRef**: resolución y verificación de DOI.

## Trabajos relacionados

bib_exprés no es la primera herramienta para explorar bibliografía a partir de un paper. Algunas referencias del mismo espacio:

- **[Connected Papers](https://www.connectedpapers.com/)**: explorador visual que, a partir de un paper, dibuja un grafo de artículos relacionados por co-citación. Pensado para explorar visualmente, no para generar una bibliografía exportable con reglas configurables.
- **[ResearchRabbit](https://www.researchrabbit.ai/)**: similar en espíritu ("Spotify para papers"), con colecciones y descubrimiento por similitud y citas, también centrado en la exploración visual interactiva.
- **[Litmaps](https://www.litmaps.com/)**: mapea cómo evoluciona una red de citas en el tiempo, orientado a mantener revisiones de literatura actualizadas.
- **[ASReview](https://asreview.nl/)**: open-source, pero resuelve un problema distinto. Dado un conjunto grande de candidatos (p.ej. exportado de una base de datos), ayuda a priorizar cuáles cribar primero en una revisión sistemática, usando aprendizaje activo.

La diferencia de bib_exprés: es una herramienta de línea de comandos, librería y app de escritorio (no una app web), con un algoritmo de expansión y relevancia configurable y transparente, cuya salida es directamente un fichero de bibliografía listo para un gestor de referencias, LaTeX o Excel, no un grafo visual para explorar a mano.

## Limitaciones

- Solo encuentra lo que **OpenAlex, Semantic Scholar o CrossRef** tengan indexado. Los papers muy nuevos, muy de nicho o fuera de esas bases no van a aparecer.
- La bibliografía es siempre un **subconjunto acotado** (por generaciones y tope de artículos), no "todo lo relacionado". Es una decisión consciente (rendimiento y respeto a las APIs), no un descuido.
- El modo "similares" depende de tener configurada una API key de Semantic Scholar. Sin ella, la expansión se queda solo con el grafo de citas de OpenAlex.
- El score de relevancia es una **fórmula simple y transparente**, no un modelo de lenguaje ni *embeddings*. Prioriza poder explicar por qué algo entra o no, a costa de ser menos sofisticado que un enfoque de ML.
- El `.exe` no está firmado. Windows puede mostrar un aviso de SmartScreen la primera vez, y el antivirus puede bloquearlo brevemente nada más construirlo.
- Buscar el paper padre por ID de arXiv falla si ese paper se publicó después en otro sitio con su propio DOI (le pasa a bastantes papers de ML conocidos). Buscarlo por título no tiene este problema. Detalle en [docs/ejemplo-v2.md](docs/ejemplo-v2.md).
- El paper padre nunca se descarta por los filtros de tipo de documento o acceso abierto, ni por relevancia: siempre aparece en el resultado final.

## Hoja de ruta

**v3**, ya planificada:

- **Algoritmo mejorado y explicable**: temas de OpenAlex, conexión con los papers ya aceptados y parecido de texto, con el desglose del score visible por artículo. Se medirá contra un banco de pruebas con revisiones reales antes de cambiar nada.
- **Acceso institucional**: enlaces a través del proxy de tu biblioteca y filtro "solo accesibles para mí".
- **Filtro por idioma**, al estilo Google Scholar: en el idioma de la búsqueda o en cualquiera.
- **GUI rediseñada**, con el logo y en inglés o español, a elegir.

Preguntas abiertas:

- Los valores por defecto (`max_articles=200`, `max_fanout_per_node=20`, pesos de relevancia) son un punto de partida razonable, no un número validado. El banco de pruebas de v3 servirá para ajustarlos.
- Si compensa firmar el `.exe` (certificado de firma de código) para que Windows deje de avisar.
- Si la parte de librería/CLI se distribuye por PyPI o solo desde GitHub.

## Historial de versiones

### v2.3.0: barra de progreso, exportación a Excel, README bilingüe y adiós a los cuelgues silenciosos

- **Progreso en directo durante la búsqueda**: barra con artículos encontrados sobre el tope, generación y artículo que se está explorando, y "última actividad hace X s" para distinguir una búsqueda lenta de una colgada (a partir de 30 s avisa de que las APIs están tardando, pero la búsqueda sigue). Un botón **Cancelar** para la búsqueda y se queda con lo encontrado hasta ese momento. La CLI muestra lo mismo en una línea en `stderr`; `--quiet` la oculta.
- **Exportación a Excel para revisiones bibliográficas** (`--format xlsx`, o "Excel" en la app): título, autores, DOI como enlace, tema, palabras clave, relevancia y una columna "Otras notas" vacía. Cabecera fija y filtros, así que ordenar por autor o por relevancia es un clic. Un texto que empiece por `=` se guarda como texto, nunca como fórmula.
- **README en inglés** con versión en español (`README.es.md`), reordenado: qué hace, el benchmark, descarga y uso primero, e historial de versiones al final.
- **Arreglado: la app podía quedarse colgada horas sin decir nada** cuando OpenAlex limita las peticiones (demasiadas en poco tiempo, o la cuota diaria agotada). En ese caso OpenAlex pide esperar, a veces unas 10 horas, y bib_exprés obedecía sin límite. Ahora las esperas cortas (hasta 30 s) se reintentan como antes, y las largas paran la búsqueda al momento con un mensaje claro que dice cuánto esperar. Lo ya consultado queda en la caché local, así que reintentar más tarde gasta menos peticiones. Afectaba a todas las versiones anteriores.
- Dependencia nueva: `openpyxl`. El `.exe` pasa de ~16,4 MB a ~17 MB.

### v2.2.0: parche de seguridad, librerías desactualizadas dentro del `.exe`

Una segunda auditoría de seguridad, centrada en lo que añadió v2 (el `.exe` y la GUI), encontró que el `.exe` publicado llevaba dentro versiones de tres librerías con vulnerabilidades conocidas, publicadas *después* de construirlo:

- **`pypdf`** (lee el PDF cuando le das un PDF como paper padre): un PDF fabricado a propósito podía dejar la app colgada o comiéndose la memoria. No permitía ejecutar código, pero sí bloquear la app con un fichero que suele venir de internet.
- **`urllib3`** (la conexión HTTP con las APIs): fallos en cómo limita respuestas comprimidas muy grandes.
- **`certifi`** (la lista de autoridades de certificados en las que confía la conexión HTTPS): incluía una autoridad ya retirada.

**Arreglado**:

- Las tres librerías, actualizadas a versiones sin problemas conocidos.
- El `.exe` se construye con versiones exactas fijadas en `packaging/requirements-build.txt`.
- El CI pasa `pip-audit` **cada semana**, aunque no haya commits. La razón de fondo de este parche es que antes solo se auditaba al hacer push.
- Arreglos menores de paso:
  - Un PDF raro ya no deja la GUI esperando sin mensaje.
  - El límite de 10 MB por respuesta se aplica mientras se descarga.
  - Los ajustes ya no aceptan saltos de línea que rompan el `.env`.
- Cada release publica el SHA-256 del `.exe` ([cómo comprobarlo](docs/instalacion.md)).

No hace falta ninguna acción manual más allá de descargar el `.exe` nuevo o actualizar con `pip install -e .`.

### v2.1.1: icono propio para `bib-expres-gui.exe`

El `.exe` salía con el icono genérico de PyInstaller: el `.spec` no declaraba ninguno, y el parámetro de icono de `pywebview` solo funciona en GTK/QT, no en Windows. Se añadió `packaging/icon.ico` (nodo raíz ramificándose en tres, el *snowballing* de citas que hace la app), referenciado desde `EXE(icon=...)`. Sin cambios de comportamiento.

### v2.1.0: parche de seguridad, DOIs sin escapar en las peticiones HTTP

bib_exprés metía el DOI directamente en el path de la URL al pedir metadata a OpenAlex, CrossRef y Semantic Scholar, sin escapar caracteres especiales. Un DOI válido puede contener `/`, `:`, `;`, `(` y `)`, así que un DOI pensado para ello podía alterar la petición real enviada a esas APIs. El caso más delicado estaba en el modo "similares", donde el DOI de cada candidato viene tal cual de la respuesta de Semantic Scholar.

**Arreglado**: los cuatro sitios donde un DOI (o el ID interno de OpenAlex) se interpolaba en el path ahora lo escapan primero (`urllib.parse.quote`). Comprobado contra las tres APIs reales que un DOI normal se sigue resolviendo exactamente igual.

### v2.0.0: interfaz gráfica, `.exe` y curación

- Interfaz gráfica de escritorio (`bib-expres-gui`) y `.exe` standalone descargable.
- Curación de resultados tipo Tinder.
- Entrada por ID/URL de arXiv, título en texto libre y PDF.
- Salida en RIS y CSL-JSON, además de BibTeX.
- Filtros por tipo de documento y acceso abierto.

Validada contra datos reales y con clics reales dentro de la ventana ([ejemplo de v2](docs/ejemplo-v2.md)). Descartado por ahora: autenticación, que solo tendría sentido si esto se ofreciera como servicio a terceros.

### v1: CLI de principio a fin

Snowballing por DOI desde la línea de comandos, con salida BibTeX: 200 artículos en ~22 segundos ([ejemplo](docs/ejemplo.md)).

## Licencia

MIT. Ver [LICENSE](LICENSE).
