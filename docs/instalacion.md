# Instalación

## Requisitos

- Python 3.10 o superior.
- Un email de contacto para el `mailto` de OpenAlex/CrossRef (no hace falta registro, solo un email).
- Opcional: una [API key gratuita de Semantic Scholar](https://www.semanticscholar.org/product/api) si vas a usar el modo de expansión "similares".

## Clonar e instalar en modo desarrollo

```bash
git clone https://github.com/AIAYN-creator/Bib-Expres.git
cd Bib-Expres
pip install -e ".[dev]"
```

Esto instala el paquete en modo editable (los cambios en `src/` se reflejan sin reinstalar) junto con las dependencias de desarrollo (`pytest`).

## Configurar variables de entorno

```bash
cp .env.example .env
```

Y rellena:

- `CONTACT_EMAIL` — tu email, usado como identificación de buena fe ante OpenAlex/CrossRef (mejora los límites de peticiones, no se publica en ningún sitio).
- `SEMANTIC_SCHOLAR_API_KEY` — opcional, solo si vas a usar el modo "similares".

**El `.env` real nunca se commitea** — ya está excluido en `.gitignore`.

## Verificar la instalación

```bash
bib-expres --version
```

## Ejecutar los tests

```bash
pytest
```
