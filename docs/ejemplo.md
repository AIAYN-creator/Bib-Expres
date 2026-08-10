# Ejemplo real (validación end-to-end)

Ejecución real contra un DOI real, sin mocks ni clientes falsos — así se validó que v1 funciona de principio a fin, no solo que compila.

## Comando

```bash
bib-expres --doi 10.65215/2q58a426 --output attention.bib
```

(el DOI corresponde a "Attention Is All You Need", Vaswani et al. — confirmado consultando OpenAlex en directo antes de usarlo, no de memoria)

## Resultado

```
200 articulos escritos en attention.bib
```

- Tiempo total: ~22 segundos (parámetros por defecto: 2 generaciones, tope de 200 artículos, modos `references,citations`).
- Se alcanzó el tope de 200 artículos antes de agotar el grafo — esperable para un paper con miles de citas entrantes.
- La desambiguación de cite-keys funcionó con datos reales: varios autores repetidos en el mismo año (`zhao2018`/`zhao2018a`, `zhang2018`/`zhang2018a`...) sin colisiones.

## Primeras entradas

```bibtex
@article{vaswani2025,
  title = {Attention Is All You Need},
  author = {Ashish Vaswani and Noam Shazeer and Niki Parmar and Jakob Uszkoreit and Llion Jones and Aidan N. Gomez and Łukasz Kaiser and Illia Polosukhin},
  year = {2025},
  doi = {10.65215/2q58a426},
  url = {https://doi.org/10.65215/2q58a426},
}

@article{sun2019,
  title = {How to Fine-Tune BERT for Text Classification?},
  author = {Chi Sun and Xipeng Qiu and Yige Xu and Xuanjing Huang},
  year = {2019},
  journal = {Lecture notes in computer science},
  doi = {10.1007/978-3-030-32381-3_16},
  url = {https://doi.org/10.1007/978-3-030-32381-3_16},
}
```

Todas las entradas encontradas están genuinamente relacionadas con el paper padre (variantes de atención, fine-tuning de transformers, traducción automática neuronal) — el filtro de relevancia se está comportando como se esperaba.

## Hallazgo real: datos incompletos en la fuente

De 200 entradas, 2 llegaron con metadata incompleta directamente desde OpenAlex (no es un fallo de bib_exprés, es la fuente): un registro sin título y otro sin autores. En ambos casos el fallback ya previsto en `export.py` ("(sin título)" / "Unknown") evitó una entrada rota o el propio programa cayéndose — exactamente para lo que estaba pensado, ahora confirmado con datos reales en vez de solo en tests con fixtures.

## Checklist de "hecho" para v1 (`alcance-requisitos`)

- [x] Dado un DOI y unos parámetros, produce una bibliografía consolidada y deduplicada en BibTeX.
- [x] Funciona de principio a fin en al menos un caso real, documentado como ejemplo (esta página).
- [x] README con instalación, uso básico y limitaciones conocidas.
- [x] Sin credenciales ni secretos en el repo.
