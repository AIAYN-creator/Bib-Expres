# Experimentos condicionados del algoritmo v3 — 2026-11-14

Las dos señales que `diseno-algoritmo-v3` dejó "solo si el banco lo confirma", más la calibración del umbral. Todo sobre la implementación real (commit `7fa444e`), con la misma caché y el mismo día.

| Variante | Recall@50 | Recall@100 | Recall@200 | transformers | CRISPR | grafeno |
|---|---|---|---|---|---|---|
| **v3 tal como queda** (concepts, umbral 0,15) | **10,2 %** | **16,4 %** | **24,0 %** | 17,5 % | 50,0 % | 4,6 % |
| umbral 0 | 10,2 % | 16,4 % | 24,0 % | 17,5 % | 50,0 % | 4,6 % |
| umbral 0,3 | 10,2 % | 16,4 % | 24,0 % | 17,5 % | 50,0 % | 4,6 % |
| + TF-IDF título+abstract, peso 0,5 | 10,3 % | 16,4 % | 23,5 % | 17,5 % | 48,0 % | 5,1 % |
| + TF-IDF título+abstract, peso 1 | 9,7 % | 16,1 % | 24,0 % | 18,6 % | 48,0 % | 5,3 % |
| topics en vez de concepts | — | — | — | — | — | — |

Línea base (v2.2.0): recall@200 medio 9,9 %.

## Conclusiones

- **El umbral no influye en el banco**: con miles de candidatos en el pool, los 200 mejores siempre lo superan. Solo actúa en búsquedas pequeñas (grafos con pocos papers). Se queda en 0,15 sobre el score final, que equivale aproximadamente al 0,3 de antes sobre la relevancia temática para un paper sin conexiones ni palabras clave en común.
- **TF-IDF no aporta**: entre −0,5 y 0 puntos de media. El diseño exigía +2 puntos para incluirlo, así que **queda fuera**. Las palabras clave de OpenAlex ya recogen esa señal.
- **Topics frente a concepts: sin medir.** Cambiar la señal temática cambia qué papers se exploran, y por tanto requiere peticiones nuevas. A mitad del experimento OpenAlex agotó nuestra cuota diaria (HTTP 429, "vuelve en ~10 h"). Pendiente de repetir cuando se recupere. Mientras, se mantiene `concepts`, que OpenAlex sigue devolviendo.
