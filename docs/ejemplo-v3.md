# Ejemplo real de v3 (validación end-to-end)

Continúa [docs/ejemplo.md](ejemplo.md) (v1) y [docs/ejemplo-v2.md](ejemplo-v2.md) (v2). Aquí se valida lo nuevo de v3: el algoritmo que explora a lo ancho y elige al final, el desglose del score, el acceso institucional, el filtro de idioma y la GUI rediseñada en dos idiomas. Todo contra las APIs reales, el 14 y 15 de noviembre de 2026.

## En la ventana real: de un título a un Excel

Dentro de la ventana nativa (pywebview + WebView2), con el backend real:

1. **Buscar por título**: `Attention Is All You Need`. La app ofrece candidatos y no elige ninguno sola:
   *Attention Is All You Need* · *Attention Is All You Need In Speech Separation* · *Channel Attention Is All You Need for Video Frame Interpolation*. Se elige el primero.
2. **Parámetros por defecto**: *"Explorará hasta 21 papers"*.
3. **Resultado**: **200 artículos de 1.379 candidatos vistos**. Los cinco primeros:

   | Score | Artículo |
   |---|---|
   | 0.67 | A Survey on Vision Transformer |
   | 0.67 | BART: Denoising Sequence-to-Sequence Pre-training for Natural Language Generation… |
   | 0.66 | Cross-lingual Language Model Pretraining |
   | 0.65 | Self-Attention with Relative Position Representations |
   | 0.65 | Informer: Beyond Efficient Transformer for Long Sequence Time-Series Forecasting |

4. **"¿Por qué?"** en el primero: *relevancia temática 0.64 · conectado con 8 papers · palabras clave en común 0.06 (transformer models)*.
5. **Acceso**: de entrada, 185 *abierto*, 3 *abierto (bronze)* y 12 *sin comprobar*. Tras marcar en *Mi institución* las dos editoriales más frecuentes (Cornell University y IEEE), 1 pasa a *mi institución* y 5 a *sin acceso conocido*. *Ocultar lo que no puedo leer* deja **195**.
6. **Curación**: descartar, guardar, descartar, guardar, guardar, y **Z** deshace la última → *"Revisados 4 / 194 · 2 guardados"*.
7. **Exportar**: resumen *193 van al fichero / 2 descartados / 5 ocultos* → **Excel**: *"Guardado: 193 artículos en revision-transformers.xlsx"*. El fichero tiene 193 filas con las 10 columnas, incluidas *Por qué*, *Acceso* y *Enlace de acceso*.

El idioma de la interfaz y las editoriales marcadas quedan guardados en el `.env`.

## En la CLI

```bash
bib-expres --doi 10.48550/arxiv.1706.03762 --explain --output transformers.bib
```

```
- A Survey on Vision Transformer
    0.67 = relevancia 0.64 (tema 0.56, citas 0.93, recencia 0.87) · conectado con 8 papers de la búsqueda · comparte: transformer models
- BART: Denoising Sequence-to-Sequence Pre-training for Natural Language
    0.67 = relevancia 0.62 (tema 0.52, citas 1.00, recencia 0.80) · conectado con 6 papers de la búsqueda · comparte: machine translation
- Cross-lingual Language Model Pretraining
    0.66 = relevancia 0.71 (tema 0.68, citas 0.84, recencia 0.77) · conectado con 5 papers de la búsqueda · comparte: machine translation
```

**Acceso institucional**:

```bash
bib-expres --doi 10.48550/arxiv.1706.03762 \
  --publishers "Cornell University;Institute of Electrical and Electronics Engineers" \
  --accessible-only --strict-access \
  --library-link "https://proxy.example.edu/login?url=" --output acc.xlsx
```

Quita 10 artículos y deja 190: 185 abiertos, 3 *bronze* y 2 de las editoriales marcadas. Estos últimos llevan su enlace a través del proxy: `https://proxy.example.edu/login?url=https%3A%2F%2Fdoi.org%2F…`.

**Filtro de idioma**:

- *El análisis factorial exploratorio de los ítems* (Anales de Psicología, en español) con `--language same` → **156 artículos** en español (o sin idioma conocido), en 47 s con la caché vacía.
- *Attention Is All You Need* con `--language es` → **solo el paper de partida**. En v3 los filtros ya no cortan la exploración (hay un test con un paper en inglés que hace de puente hacia uno en español), así que el motivo es otro: **entre los 1.379 candidatos alcanzables desde AIAYN no hay ninguno en español**. Es lo que hay en los datos, no una limitación del filtro.

## El algoritmo, con la caché vacía

**Banco de pruebas** (`benchmarks/run_benchmark.py`, tres revisiones reales; tabla en `benchmarks/results/2026-11-15-v3-final.md`):

| Caso | Recall@200 v2.2 | Recall@200 v3 |
|---|---|---|
| transformers (AIAYN) | 8,2 % | 17,5 % |
| CRISPR | 18,6 % | 50,0 % |
| grafeno | 2,9 % | 4,6 % |
| **media** | **9,9 %** | **24,0 %** |

Exactamente la misma cifra que con la caché del día anterior: el resultado es reproducible.

**Topics frente a concepts** (pendiente desde la implementación): con *topics*, la media sube algo (24,4 %), pero el caso de transformers cae de 17,5 % a 9,3 % y el recall@50 baja de 10,2 % a 8,5 %. **Se mantiene `concepts`**, como fijaba el diseño ("solo si no empeora").

**Tiempo**, AIAYN con los parámetros por defecto y la caché vacía, contando peticiones reales:

| Versión | Tiempo | Peticiones a las APIs |
|---|---|---|
| v2.3.0 | 36,1 s | 36 |
| v3 | 55,2 s | 74 |

**v3 tarda 1,53 veces lo de v2.3**, justo por encima del límite de 1,5× que se fijó en el diseño. **Decisión: se acepta** como coste de la mejora (unos 20 s más por búsqueda a cambio de 2,4 veces más bibliografía relevante encontrada), sin tocar la exploración por defecto. El tiempo va casi en proporción a las peticiones: v3 expande 21 papers en lugar de unos 10, porque explora todo antes de elegir. Es lo que compra el salto del 9,9 % al 24 % de recall. Las mediciones son de una sola ejecución con la red de ese momento, y OpenAlex varía bastante de un día a otro (la misma búsqueda de v2.3 ha tardado entre 27 y 39 s otros días).

## Límite de OpenAlex: 1.000 peticiones al día

Durante la validación se agotó la cuota de OpenAlex. Sus cabeceras muestran un presupuesto gratuito de **0,10 $ al día a 0,0001 $ por petición, es decir, unas 1.000 peticiones**. Una búsqueda por defecto de v3 hace unas 75, así que da para **unas 13 búsquedas nuevas al día**. Las repetidas salen de la caché local y no cuentan. Desde v2.3.0, al agotarse la cuota la app avisa con un mensaje claro en vez de quedarse colgada.
