# Hoja de ruta

[English](ROADMAP.md) · **Español**

De dónde viene bib_exprés y hacia dónde podría ir. Las notas completas de cada versión publicada están en el [historial de versiones del README](README.es.md#historial-de-versiones).

## Publicado

| Versión | Tema | Lo principal |
|---|---|---|
| **v1** | Funciona | DOI → snowballing (referencias + citas) → BibTeX, desde la línea de comandos. 200 artículos en ~22 s. |
| **v2.0.0** | Sin terminal | App de escritorio y `.exe` independiente, curación tipo Tinder, entrada por arXiv/título/PDF, RIS y CSL-JSON, filtros por tipo de documento y acceso abierto. |
| v2.1.0 · v2.1.1 | Robustez | DOIs escapados en las peticiones a las APIs (seguridad) · icono propio. |
| v2.2.0 | Robustez | Librerías desactualizadas del `.exe` puestas al día, build con versiones fijadas, auditoría semanal de vulnerabilidades. |
| **v2.3.0** | Se siente viva | Barra de progreso con cancelar, exportación a Excel para revisiones bibliográficas, README bilingüe, adiós a los cuelgues silenciosos cuando OpenAlex limita las peticiones. |
| **v3.0.0** | Encuentra más y explica por qué | Algoritmo nuevo (explorar ancho, elegir al final): recall@200 del 9,9 % al 24 % en revisiones reales, con cada score explicado. Acceso institucional, filtro de idioma, app rediseñada en español e inglés, cuota diaria de OpenAlex a la vista. |
| **v3.1.0** | Te deja irte | Aviso del sistema cuando una búsqueda termina mientras estás en otra ventana, y moverse libremente entre pantallas ("Nueva búsqueda" tras exportar, pasos y logo clicables). |

## Siguiente: ideas, todavía sin planificar

- **Listados de revistas de la biblioteca (KBART)**: saber exactamente qué cubre tu biblioteca por revista y año, si las bibliotecas lo ofrecen. Hoy el acceso institucional es aproximado (acceso abierto + las editoriales que marques).
- **Volver a probar los *topics* de OpenAlex** en lugar de los *concepts* cuando mejore su cobertura. Hoy bajan el recall en uno de los tres casos del banco de pruebas.
- **Más casos en el banco de pruebas**, de otros campos, para ajustar los valores por defecto con más de tres revisiones. Añadir uno son dos DOIs en `benchmarks/cases.json` ([cómo](CONTRIBUTING.md#the-benchmark)).
- **Gastar menos de la cuota gratuita de OpenAlex** (~13 búsquedas nuevas al día), p.ej. reaprovechando más de lo que ya trajeron búsquedas anteriores.

## Preguntas abiertas

- Si compensa firmar el `.exe` (certificado de firma de código) para que Windows deje de avisar.
- Si la parte de librería/CLI se distribuye por PyPI o solo desde GitHub.
- Si los mensajes de la CLI (todavía en español) deberían seguir a la app y ser bilingües.

Las ideas y los votos son bienvenidos: abre un *issue* o mira [CONTRIBUTING.md](CONTRIBUTING.md).
