# Ejemplo real de v2 (validación end-to-end)

Continúa [docs/ejemplo.md](ejemplo.md) (la validación de v1) — aquí se valida lo nuevo de v2: entrada por título/arXiv, formatos RIS/CSL-JSON, filtros por metadatos, y el `.exe` standalone. Todo contra APIs reales, sin mocks.

## Resolución por título, con confirmación — RIS

```bash
bib-expres --input "Deep Residual Learning for Image Recognition" --output resnet.ris --format ris
```

La CLI encontró varios candidatos reales y pidió confirmar:

```
Varios resultados para 'Deep Residual Learning for Image Recognition':
  1. Deep Residual Learning for Image Recognition (2016) -- Kaiming He, Xiangyu Zhang, Shaoqing Ren
  2. Deep Residual Learning for Image Recognition (2015) -- He, Kaiming, Xiangyu Zhang, Shaoqing Ren
  3. Deep Residual Learning for Image Recognition: A Survey (2022) -- Muhammad Shafiq, Zhaoquan Gu
  4. ImageNet classification with deep convolutional neural networks (2017) -- Alex Krizhevsky, Ilya Sutskever, Geoffrey E. Hinton
  5. A survey on deep learning in medical image analysis (2017) -- Geert Litjens, Thijs Kooi, Babak Ehteshami Bejnordi
Elige un numero (Enter para cancelar): 1
```

Confirmado el candidato correcto (opción 1, el ResNet real — DOI `10.1109/cvpr.2016.90`), la búsqueda expandió y exportó a RIS:

```ris
TY  - JOUR
TI  - Deep Residual Learning for Image Recognition
AU  - Kaiming He
AU  - Xiangyu Zhang
AU  - Shaoqing Ren
AU  - Jian Sun
PY  - 2016
DO  - 10.1109/cvpr.2016.90
UR  - https://doi.org/10.1109/cvpr.2016.90
ER  -
```

Los 14 artículos siguientes son genuinamente relacionados (MobileNetV2, Identity Mappings in Deep Residual Networks —un seguimiento del propio ResNet por los mismos autores—, Faster R-CNN, Focal Loss...). El campo `T2` (venue) aparece solo cuando el candidato tiene uno — se omite limpio cuando no, igual que en BibTeX.

## Resolución por arXiv — límite real encontrado, no solo teórico

Con un ID de arXiv de un paper que **también se publicó después en una conferencia** (el caso más común para papers de ML conocidos):

```bash
bib-expres --input "1706.03762" --output x.bib   # "Attention Is All You Need"
```

```
Error: El DOI de arXiv construido para '1706.03762' ('10.48550/arXiv.1706.03762') es valido,
pero OpenAlex/CrossRef no lo tienen como DOI principal de ese trabajo -- pasa cuando el paper
se publico despues en una revista o conferencia con su propio DOI. Prueba a buscarlo por su
titulo en su lugar.
```

**Investigado en directo, no asumido**: el DOI construido (`10.48550/arXiv.1706.03762`) **sí existe y resuelve de verdad** (confirmado contra `doi.org/api/handles/...`) — apunta a `arxiv.org/abs/1706.03762`. El problema es que OpenAlex indexa este paper bajo su DOI "oficial" de publicación (`10.65215/2q58a426`) como DOI *principal*, y el de arXiv queda solo como una de sus 11 ubicaciones alternativas — invisible para una búsqueda directa por DOI (probado también con el filtro general de la API, mismo resultado: 0). No es un fallo de `bib_exprés` ni de la construcción del DOI — es cómo OpenAlex indexa DOIs alternativos. El mensaje de error se corrigió durante esta validación para explicar esto y sugerir la vía que sí funciona (buscar por título), en vez de repetir "DOI no encontrado" como si el usuario hubiera escrito un DOI a mano.

Con un arXiv ID que sí es el DOI principal en OpenAlex (un paper sin publicación posterior aparte, o donde arXiv es la referencia canónica) funciona directo:

```bash
bib-expres --input "2312.11805" --output gemini.json --format csljson   # "Gemini: A Family of Highly Capable Multimodal Models"
```

```
12 articulos escritos en gemini.json
```

CSL-JSON válido, DOI correcto (`10.48550/arxiv.2312.11805`). Efecto secundario útil de este caso: el paper tiene **1351 autores** (habitual en papers de laboratorios grandes) — la exportación los manejó todos sin romperse, buena señal de robustez no buscada a propósito. Sí confirmó el límite ya conocido de `_split_name` (heurística de última-palabra-es-apellido): un autor cuyo nombre en OpenAlex ya venía como `"Nick, Fernando,"` (formato apellido-primero con coma) se separó en `family="Nick"` / `given="Fernando,"` — con la coma colgando. Es exactamente el riesgo que `export.py` ya declaraba conocido, ahora confirmado con datos reales en vez de solo en teoría.

## Filtros por metadatos contra datos reales

Sobre el mismo paper padre (ResNet), un hallazgo real sobre cómo interactúa el filtro con el paper padre:

```
Sin filtros:        21 resultados -- tipos {conference-paper: 9, article: 8, book-review: 1, preprint: 3}, 10 open access
Solo --doc-types article:   14 resultados, 1 no-article colado
Solo --open-access-only:    21 resultados, 0 no-OA colados
```

El "1 no-article colado" con el filtro de tipo es **el propio paper padre** (ResNet es `conference-paper`, no `article`) — y es comportamiento correcto, no un bug: el paper padre nunca se descarta por relevancia (`diseno-relevancia`, v1, ya lo dejaba así — "es el punto de partida, no un resultado a evaluar"), y los filtros de metadatos heredan la misma exención al vivir en el mismo punto del código. No estaba escrito explícitamente en `diseno-filtros-metadatos-v2`, así que queda documentado aquí: **el paper padre siempre aparece en el resultado, sin importar los filtros de tipo/acceso abierto que se pidan.**

## El `.exe` standalone

Reconstruido de cero para esta validación (con curación tipo Tinder ya incluida, que no estaba en el build de la noche anterior):

- **15 MB**, arrancó limpio, título de ventana correcto, proceso respondiendo.
- Durante el build, Windows intentó bloquear brevemente el `.exe` recién escrito (`PermissionError` en `update_exe_pe_checksum`, reintentado automáticamente por PyInstaller hasta que funcionó) — evidencia en vivo de exactamente el riesgo de falso-positivo de antivirus que `diseno-empaquetado-exe-v2` ya anticipaba, no solo una preocupación teórica.
- **Sin secretos embebidos**: se comprobó a propósito que el email real de `CONTACT_EMAIL` del `.env` de esta máquina *no* aparece en ningún punto de los bytes del `.exe` — se lee en tiempo de ejecución, nunca se hornea en el build.
- `pip-audit` limpio sobre el entorno de build (incluyendo `pyinstaller` y sus dependencias) — los únicos avisos siguen siendo sobre la versión de `pip`, no del proyecto.

## Checklist de "hecho" para v2 (`alcance-v2`)

- [x] Existe un `.exe` descargable que no requiere Python ni terminal instalados — construido y verificado dos noches distintas, arranca standalone.
- [x] Desde la GUI: introducir un DOI (u otro formato aceptado) y los parámetros de búsqueda, lanzar la búsqueda y ver los candidatos — confirmado en vivo por el usuario (avanza a parámetros, "búsqueda muy eficiente").
- [x] Poder revisar los candidatos uno a uno (abstract) y decidir guardar/descartar antes de exportar — implementado, probado por unidad, y **probado a mano dentro de la ventana real por el usuario, con clics de verdad** (build reconstruido de cero para esta prueba, con curación ya incluida).
- [x] Exportar el resultado final a fichero — BibTeX, RIS y CSL-JSON, los tres probados contra datos reales en esta misma página, y el flujo completo de exportar también confirmado a mano desde la GUI.
- [x] README y documentación de usuario actualizados para el perfil no técnico.
- [x] Sin credenciales ni secretos nuevos expuestos por el `.exe` — verificado arriba, no solo asumido.

Con esto, v2 está completo según `alcance-v2`, con las 6 condiciones cerradas: validado con datos reales (esta página), con una sesión completa de clics reales dentro de la ventana del `.exe` — identificar paper, ajustar parámetros, buscar, curar candidatos y exportar — y publicado como descarga directa en [GitHub Releases](https://github.com/AIAYN-creator/Bib-Expres/releases/latest).
