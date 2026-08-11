# Instalación

## Descargar el `.exe` (recomendado si no vas a usar la CLI)

**[Descarga `bib-expres-gui.exe` desde Releases](https://github.com/AIAYN-creator/Bib-Expres/releases/latest)** (~15 MB) y ejecútalo — no hace falta instalar Python ni nada más. Ese enlace apunta siempre a la última versión publicada.

Windows puede avisar la primera vez porque el `.exe` no está firmado ("Windows protegió tu PC" → "Más información" → "Ejecutar de todas formas") — es un aviso conocido, no significa que algo vaya mal.

El resto de esta página es para quien quiera la CLI, tocar el código, o construir el `.exe` en su propia máquina en vez de descargarlo.

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

## Interfaz gráfica

Alternativa a la CLI para quien prefiera no usar terminal. Con el paquete instalado (paso anterior), se lanza igual que la CLI:

```bash
bib-expres-gui
```

Abre una ventana de escritorio (usa el motor web del propio sistema — WebView2 en Windows, ya viene con Windows 10/11) con un formulario para el paper de entrada (DOI, ID/URL de arXiv, título o PDF), los parámetros de búsqueda, y exportación a BibTeX/RIS/CSL-JSON. Entre la búsqueda y la exportación hay una pantalla opcional de curación tipo Tinder: revisar cada candidato (con su abstract) y decidir guardar o descartar uno a uno, con botones, flechas del teclado o arrastrando la tarjeta. El email de contacto y la API key de Semantic Scholar también se pueden configurar desde dentro (icono de Ajustes), sin tocar el `.env` a mano.

Probada de principio a fin con clics reales (no solo con tests automáticos): resolver un paper, ajustar parámetros, buscar, curar candidatos y exportar, todo funcionando.

## Construir el `.exe` standalone tú mismo

Alternativa a descargarlo de Releases (arriba) — para verificar el build, modificar el código, o generarlo en una plataforma sin release publicado. Requiere haber clonado el repo:

```bash
pip install -e ".[packaging]"
pyinstaller packaging/bib-expres-gui.spec
```

El resultado queda en `dist/bib-expres-gui.exe` (~15 MB) — un único fichero, sin dependencias externas salvo el WebView2 que Windows 10/11 ya trae de fábrica. Como no está firmado, Windows puede mostrar un aviso de SmartScreen la primera vez ("Más información" > "Ejecutar de todas formas"), y el antivirus puede bloquearlo brevemente justo al terminar de construirlo (pasa de verdad, no es solo teórico).

## Ejecutar los tests

```bash
pytest
```
