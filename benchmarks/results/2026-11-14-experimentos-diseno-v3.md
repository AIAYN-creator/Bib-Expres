# Experimentos para el diseño del algoritmo v3 — 2026-11-14

Variantes probadas con un prototipo desechable sobre los tres casos de `cases.json`, el mismo día y con la misma caché, para que sean comparables. Configuración común: 2 generaciones, tope de 200 artículos.

**Pool**: explorar el grafo entero (mismas generaciones y fanout) guardando *todos* los candidatos vistos, y elegir al final los 200 mejores por score combinado, en vez de quedarse con los primeros que superan el umbral.

**Conexiones**: cuántas veces aparece un candidato entre las referencias o citas de los papers explorados.

**Palabras clave**: solapamiento (Jaccard) con las palabras clave del paper de partida.

| Variante | Citas por paper | Selección | Recall@50 | Recall@100 | Recall@200 | Prec@50 (media) | Tiempo por caso |
|---|---|---|---|---|---|---|---|
| A — actual (v2.2.0) | 50 | por orden de llegada | 4,9 % | 8,4 % | 9,9 % | 14,7 % | 17–37 s |
| B — más citas | 200 | igual | 3,7 % | 4,9 % | 6,4 % | 10,7 % | 25–118 s |
| C — más citas + fanout 40 | 200 | igual | 4,2 % | 6,5 % | 10,1 % | 12,7 % | — |
| D — pool + conexiones (peso 0,4) | 200 | pool | 5,6 % | 10,3 % | 17,5 % | 18,7 % | 33–47 s |
| E — pool + conexiones (peso 1) | 200 | pool | 6,0 % | 11,4 % | 19,8 % | 20,7 % | — |
| F — pool + conexiones + palabras clave | 200 | pool | 6,8 % | 11,9 % | 20,4 % | 23,3 % | — |
| G — como F, conexiones peso 2 | 200 | pool | 6,7 % | 12,2 % | 20,7 % | 22,7 % | — |
| H — como F, fanout 40 | 200 | pool | 6,3 % | 11,4 % | 19,0 % | 18,7 % | 75–89 s |
| **I — como F, 50 citas** | **50** | **pool** | **9,5 %** | **15,7 %** | **23,2 %** | **28,0 %** | **9–24 s** |
| J — como I, 50 citas *más antiguas* | 50 | pool | 4,0 % | 8,2 % | 12,4 % | 11,3 % | 32–66 s |

"—": misma búsqueda que la fila anterior ya en caché; el tiempo no es representativo.

Detalle de la variante I por caso: transformers 14,9 %, CRISPR 50,0 %, grafeno 4,6 % (recall@200).

## Conclusiones

1. **Lo que más mejora es cómo se elige, no qué llega.** Pasar a "pool + conexiones" duplica el recall@200 con los mismos candidatos.
2. **Más citas por paper empeora.** Pedir 200 en vez de 50 llena el pool de papers muy citados pero de otros temas, que diluyen el resultado (B frente a A, E/F frente a I). El diagnóstico de la tarjeta de evaluación apuntaba lo contrario: medía solo el primer salto, sin la selección.
3. **El orden por defecto de OpenAlex ya es por número de citas** (comprobado en directo). No era arbitrario, como se creyó al principio. En v3 se pedirá explícitamente (`sort=cited_by_count:desc`), para que quede documentado y no dependa de un comportamiento implícito.
4. **Las citas más antiguas no ayudan** (J).
5. **Explorar más ancho (fanout 40) no compensa**: más del doble de tiempo y no mejora.
6. **El caso del grafeno sigue bajo** (~5 %) en todas las variantes. Su revisión cita 455 papers, muchos de teoría anteriores al paper de partida, a más de dos saltos.
