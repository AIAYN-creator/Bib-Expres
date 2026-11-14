# Instalación

## Descargar el `.exe` (recomendado si no vas a usar la CLI)

**[Descarga `bib-expres-gui.exe` desde Releases](https://github.com/AIAYN-creator/Bib-Expres/releases/latest)** (~17 MB) y ejecútalo — no hace falta instalar Python ni nada más. Ese enlace apunta siempre a la última versión publicada.

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

Ojo: la API key se guarda **en texto plano** en ese `.env` (también cuando la configuras desde los Ajustes de la GUI, que escribe el `.env` en la carpeta desde la que abres la app). Es lo normal en una app de escritorio local, pero no compartas esa carpeta tal cual (un zip, una carpeta sincronizada con otra gente…) sin quitar antes el `.env`.

## Verificar la instalación

```bash
bib-expres --version
```

## Interfaz gráfica

Alternativa a la CLI para quien prefiera no usar terminal. Con el paquete instalado (paso anterior), se lanza igual que la CLI:

```bash
bib-expres-gui
```

Abre una ventana de escritorio (usa el motor web del propio sistema — WebView2 en Windows, ya viene con Windows 10/11) con un formulario para el paper de entrada (DOI, ID/URL de arXiv, título o PDF), los parámetros de búsqueda, y exportación a BibTeX/RIS/CSL-JSON o Excel. Durante la búsqueda hay una barra de progreso con el artículo que se está explorando y "última actividad hace X s" (si pasa de 30 s avisa de que las APIs están tardando, pero la búsqueda sigue), y un botón para cancelar quedándote con lo encontrado hasta ese momento. Entre la búsqueda y la exportación hay una pantalla opcional de curación tipo Tinder: revisar cada candidato (con su abstract) y decidir guardar o descartar uno a uno, con botones, flechas del teclado o arrastrando la tarjeta. El email de contacto y la API key de Semantic Scholar también se pueden configurar desde dentro (icono de Ajustes), sin tocar el `.env` a mano.

Probada de principio a fin con clics reales (no solo con tests automáticos): resolver un paper, ajustar parámetros, buscar, curar candidatos y exportar, todo funcionando.

## Construir el `.exe` standalone tú mismo

Alternativa a descargarlo de Releases (arriba) — para verificar el build, modificar el código, o generarlo en una plataforma sin release publicado. Requiere haber clonado el repo:

```bash
pip install -r packaging/requirements-build.txt
pip install --no-deps -e .
pyinstaller packaging/bib-expres-gui.spec
```

`packaging/requirements-build.txt` fija las versiones exactas que van dentro del `.exe` (el `pyproject.toml` solo pone mínimos). Así el binario no depende de lo que tengas instalado ese día, y el CI pasa `pip-audit` sobre ese fichero cada semana para avisar si sale una vulnerabilidad nueva en algo que ya está publicado. Con `pip install -e ".[packaging]"` también funciona, pero empaqueta las versiones que haya en tu entorno.

Cada release publica el **SHA-256** del `.exe`. Para comprobar que lo que has descargado es exactamente lo que se subió, en PowerShell:

```powershell
Get-FileHash .ib-expres-gui.exe -Algorithm SHA256
```

El resultado queda en `dist/bib-expres-gui.exe` (~17 MB) — un único fichero, sin dependencias externas salvo el WebView2 que Windows 10/11 ya trae de fábrica. Como no está firmado, Windows puede mostrar un aviso de SmartScreen la primera vez ("Más información" > "Ejecutar de todas formas"), y el antivirus puede bloquearlo brevemente justo al terminar de construirlo (pasa de verdad, no es solo teórico).

## Ejecutar los tests

```bash
pytest
```
