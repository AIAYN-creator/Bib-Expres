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

## Instalación

```bash
pip install -e ".[dev]"
```

Guía completa, con configuración de `.env`: [docs/instalacion.md](docs/instalacion.md).

## Uso

```bash
bib-expres --doi 10.1000/ejemplo --output bibliografia.bib
```

Referencia completa de parámetros: [docs/uso.md](docs/uso.md).

## Trabajos relacionados

bib_exprés no es la primera herramienta para explorar bibliografía a partir de un paper. Algunas referencias del mismo espacio:

- **[Connected Papers](https://www.connectedpapers.com/)** — explorador visual: a partir de un paper, dibuja un grafo de artículos relacionados por co-citación. Pensado para explorar visualmente, no para generar una bibliografía exportable con reglas configurables.
- **[ResearchRabbit](https://www.researchrabbit.ai/)** — similar en espíritu ("Spotify para papers"), con colecciones y descubrimiento por similitud/citas, también centrado en exploración visual interactiva.
- **[Litmaps](https://www.litmaps.com/)** — mapea cómo evoluciona una red de citas en el tiempo, orientado a mantener revisiones de literatura actualizadas.
- **[ASReview](https://asreview.nl/)** — open-source, pero resuelve un problema distinto: dado un conjunto grande de candidatos (p.ej. exportado de una base de datos), ayuda a priorizar cuáles cribar primero para una revisión sistemática, usando aprendizaje activo.

La diferencia de bib_exprés: es una herramienta de línea de comandos y librería (no una app web), con un algoritmo de expansión y relevancia configurable y transparente, cuya salida es directamente un fichero de bibliografía (BibTeX) listo para un gestor de referencias o LaTeX — no un grafo visual para explorar a mano.

## Limitaciones

- v1 solo acepta un **DOI** como entrada — ni arXiv ID, ni título, ni PDF (ver "Qué queda para v2").
- Solo encuentra lo que **OpenAlex, Semantic Scholar o CrossRef** tengan indexado — papers muy nuevos, muy de nicho, o fuera de esas bases no van a aparecer.
- La bibliografía es siempre un **subconjunto acotado** (por generaciones y tope de artículos), no "todo lo relacionado" — es una decisión consciente (rendimiento y respeto a las APIs), no un descuido.
- El modo "similares" depende de tener configurada una API key de Semantic Scholar — sin ella, la expansión se queda solo con el grafo de citas de OpenAlex.
- El score de relevancia es una **fórmula simple y transparente**, no un modelo de lenguaje ni embeddings — prioriza poder explicar por qué algo entra o no, a costa de ser menos sofisticado que un enfoque de ML.
- BibTeX es el único formato de salida

## Qué queda para v2

- Aceptar como entrada un ID/URL de arXiv, un título en texto libre (con confirmación), o subir un PDF y extraer el DOI/título automáticamente.
- Filtrar por tipo de documento o estado de acceso abierto — los datos ya se guardan, pero v1 no filtra por ellos.
- Hacer una interfaz de usuario más "beginner friendly", incluso empaquetarlo como un `.exe` descargable (viable con PyInstaller o similar, sin depender de tener Python instalado)
- Si algún día se expone como servicio para terceros (no solo CLI/librería local), añadir autenticación/autorización — hoy no aplica porque todo corre en local.
- Configuración a varios formatos de salida

## Preguntas abiertas

- Los valores por defecto (`max_articles=200`, `max_fanout_per_node=20`, pesos de relevancia) son un punto de partida razonable, no un número validado — probablemente haga falta ajustarlos con casos reales.
- Si el proyecto crece más allá de un uso personal/de equipo, falta decidir cómo se distribuye (¿PyPI? ¿solo instalación desde GitHub?).
- Formatos de salida más allá de BibTeX (RIS, CSL-JSON...) — no descartado, simplemente no se ha planteado todavía.

## Licencia

MIT — ver [LICENSE](LICENSE).
